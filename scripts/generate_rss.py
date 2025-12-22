#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator

This script collects Zscaler release notes from help.zscaler.com by:
- Discovering and aggregating RSS feeds from all subpages (https://help.zscaler.com/rss and subdirectories)
- Using the complete sitemap to find all potential RSS feed locations
- Parsing native RSS feeds from Zscaler's help site for all products and sections
- Falling back to page scraping if RSS feeds are unavailable
- Supporting automatic discovery of future pages and years
- Optionally limiting the feed with BACKFILL_DAYS (default: 14, e.g., 90)

Requirements:
  pip install requests beautifulsoup4 feedgen python-dateutil lxml
"""

import os
import re
import io
import gzip
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from dateutil import parser as dateparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

BASE = "https://help.zscaler.com"
SITEMAP_URL = f"{BASE}/sitemap.xml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/2.0; +https://www.zscaler.com)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")

# Relevance hints for pages from the sitemap
# We specifically consider Release Notes and What's New paths.
URL_INCLUDE_HINTS = [
    "release-notes",        # typical paths for Release Notes
    "whats-new",            # What's New overview
    "what's-new",           # alternative spelling
]
# Optional: additional hints, but use with caution (too broad means noise)
# URL_INCLUDE_HINTS += ["release", "notes"]

# Exclusion patterns (to avoid obvious non-articles)
URL_EXCLUDE_HINTS = [
    "/tag/", "/taxonomy/", "/author/", "/search", "/attachment", "/node/",
]

# Minimal pause between fetches (polite crawling) - only used in sequential operations
FETCH_DELAY_SEC = 0.3

# Concurrency settings for parallel operations
MAX_WORKERS = 10  # Max concurrent threads for network operations

# Common RSS feed paths to check
RSS_PATHS = [
    "/rss",
    "/rss.xml",
    "/feed",
    "/feed.xml",
    "/atom.xml",
]

# RSS MIME types to check
RSS_MIME_TYPES = ['xml', 'rss', 'atom']

# Maximum number of section pages to check for RSS links
MAX_SECTION_PAGES_TO_CHECK = 10

# Global session for connection pooling
_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def get_session() -> requests.Session:
    """Get or create a global requests session for connection pooling. Thread-safe."""
    global _session
    if _session is None:
        with _session_lock:
            # Double-check pattern to avoid race condition
            if _session is None:
                _session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=MAX_WORKERS,
                    pool_maxsize=MAX_WORKERS,
                    max_retries=3,
                    pool_block=False  # Raise exception instead of blocking when pool is exhausted
                )
                _session.mount('http://', adapter)
                _session.mount('https://', adapter)
                _session.headers.update(HEADERS)
    return _session


def fetch(url: str, timeout: int = 30) -> str:
    session = get_session()
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    session = get_session()
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def maybe_decompress_sitemap(url: str, content: bytes) -> bytes:
    """
    Decompress if URL ends with .gz or content is actually gzipped.
    """
    try:
        # If it looks like gzip, try to decompress
        if url.lower().endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                return gz.read()
        # Some servers send unmarked gzip data; heuristic attempt
        if content[:2] == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                return gz.read()
    except Exception as e:
        print(f"[WARN] Gzip decompression failed for {url}: {e}")
    return content


def is_help_domain(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and p.netloc.endswith("help.zscaler.com")
    except Exception:
        return False


def parse_sitemap(url: str) -> List[str]:
    """
    Loads sitemap.xml or a sub-sitemap. Supports sitemapindex recursively and .xml.gz.
    Returns a flat list of all <loc> URLs.
    Uses parallel fetching for nested sitemaps.
    """
    try:
        raw = fetch_bytes(url)
        content = maybe_decompress_sitemap(url, raw)
    except Exception as e:
        print(f"[WARN] Failed to fetch sitemap: {url} -> {e}")
        return []

    try:
        root = ET.fromstring(content)
    except Exception as e:
        print(f"[WARN] Failed to parse sitemap XML: {url} -> {e}")
        return []

    def localname(tag: str) -> str:
        return tag.split("}")[-1]

    urls: List[str] = []

    tag = localname(root.tag)
    if tag == "sitemapindex":
        # Extract all nested sitemap URLs
        nested_sitemaps = []
        for sm in root:
            if localname(sm.tag) != "sitemap":
                continue
            loc_el = next((c for c in sm if localname(c.tag) == "loc"), None)
            if loc_el is not None and loc_el.text:
                nested_sitemaps.append(loc_el.text.strip())
        
        # Parallel fetch of nested sitemaps
        if nested_sitemaps:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_url = {
                    executor.submit(parse_sitemap, sitemap_url): sitemap_url
                    for sitemap_url in nested_sitemaps
                }
                for future in as_completed(future_to_url):
                    try:
                        urls.extend(future.result())
                    except Exception as e:
                        sitemap_url = future_to_url[future]
                        print(f"[WARN] Error parsing nested sitemap {sitemap_url}: {e}")
        return urls

    if tag == "urlset":
        for u in root:
            if localname(u.tag) != "url":
                continue
            loc_el = next((c for c in u if localname(c.tag) == "loc"), None)
            if loc_el is not None and loc_el.text:
                urls.append(loc_el.text.strip())

    # Generic fallback: collect all <loc>
    if not urls:
        for el in root.iter():
            if localname(el.tag) == "loc" and el.text:
                urls.append(el.text.strip())

    return urls


def discover_rss_feeds(base_url: str, sitemap_urls: List[str]) -> Set[str]:
    """
    Discover RSS feeds from the help.zscaler.com site.
    
    Strategies:
    1. Check common RSS paths at base URL (/rss, /feed, etc.)
    2. Extract unique path prefixes from sitemap URLs (e.g., /zia/, /zpa/, /zdx/)
    3. Check for RSS feeds at each product/section path
    4. Look for RSS feed links in HTML pages
    
    Uses parallel execution for improved performance.
    
    Returns a set of discovered RSS feed URLs.
    """
    discovered_feeds: Set[str] = set()
    
    def validate_rss_url(rss_url: str) -> Optional[str]:
        """
        Validate if a URL is a valid RSS feed.
        Returns the URL if valid, None otherwise.
        """
        try:
            session = get_session()
            response = session.head(rss_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                # Verify it's actually an RSS/XML feed
                content_type = response.headers.get('content-type', '').lower()
                if any(mime_type in content_type for mime_type in RSS_MIME_TYPES):
                    return rss_url
                else:
                    # Try GET to check content
                    try:
                        content = fetch(rss_url)
                        if '<rss' in content.lower() or '<feed' in content.lower():
                            return rss_url
                    except Exception:
                        pass
        except Exception:
            pass
        return None
    
    # 1. Check common RSS paths at base URL
    print(f"[INFO] Checking for RSS feeds at base URL...")
    base_rss_urls = [urljoin(base_url, rss_path) for rss_path in RSS_PATHS]
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(validate_rss_url, url): url for url in base_rss_urls}
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                discovered_feeds.add(result)
                print(f"[INFO] Found RSS feed: {result}")
    
    # 2. Extract unique path prefixes from sitemap URLs
    # These represent different product sections (e.g., /zia/, /zpa/, /zdx/, etc.)
    path_prefixes: Set[str] = set()
    for url in sitemap_urls:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            # Take first 1-2 path segments as potential product/section identifier
            prefix = '/' + path_parts[0]
            path_prefixes.add(prefix)
            if len(path_parts) > 1:
                prefix2 = '/' + '/'.join(path_parts[:2])
                path_prefixes.add(prefix2)
    
    print(f"[INFO] Found {len(path_prefixes)} unique path prefixes from sitemap")
    
    # 3. Check for RSS feeds at each product/section path (parallel)
    section_rss_urls = []
    for prefix in sorted(path_prefixes):
        for rss_path in RSS_PATHS:
            section_rss_urls.append(urljoin(base_url, prefix + rss_path))
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(validate_rss_url, url): url for url in section_rss_urls}
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                discovered_feeds.add(result)
                print(f"[INFO] Found RSS feed: {result}")
    
    # 4. Look for RSS feed links in the main help page and key pages
    key_pages = [base_url]
    for prefix in list(path_prefixes)[:MAX_SECTION_PAGES_TO_CHECK]:
        key_pages.append(urljoin(base_url, prefix))
    
    def find_rss_in_page(page_url: str) -> Set[str]:
        """Find RSS feed links in an HTML page."""
        feeds = set()
        try:
            html = fetch(page_url)
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for RSS link tags
            for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
                href = link.get('href')
                if href:
                    feed_url = urljoin(page_url, href)
                    if is_help_domain(feed_url):
                        feeds.add(feed_url)
            
            # Look for RSS links in HTML
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if any(rss_hint in href.lower() for rss_hint in ['rss', 'feed', 'atom']):
                    feed_url = urljoin(page_url, href)
                    if is_help_domain(feed_url):
                        feeds.add(feed_url)
        except Exception:
            pass
        return feeds
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {
            executor.submit(find_rss_in_page, page_url): page_url
            for page_url in key_pages
        }
        for future in as_completed(future_to_page):
            try:
                feeds = future.result()
                for feed_url in feeds:
                    if feed_url not in discovered_feeds:
                        discovered_feeds.add(feed_url)
                        print(f"[INFO] Found RSS feed via HTML: {feed_url}")
            except Exception as e:
                pass
    
    return discovered_feeds


def parse_rss_feed(feed_url: str) -> List[Dict]:
    """
    Parse an RSS or Atom feed and extract items.
    
    Returns a list of items with: title, link, published, source_page
    """
    items: List[Dict] = []
    
    try:
        content = fetch(feed_url)
        
        # Validate content is XML before parsing
        if not content or not isinstance(content, str):
            print(f"[WARN] Invalid content type from {feed_url}")
            return items
        
        # Check if content looks like XML
        if not ('<rss' in content.lower() or '<feed' in content.lower() or '<?xml' in content.lower()):
            print(f"[WARN] Content from {feed_url} doesn't appear to be XML/RSS")
            return items
        
        root = ET.fromstring(content.encode('utf-8'))
        
        def localname(tag: str) -> str:
            return tag.split("}")[-1]
        
        root_tag = localname(root.tag)
        
        # Handle RSS 2.0
        if root_tag == "rss":
            for channel in root:
                if localname(channel.tag) != "channel":
                    continue
                for item in channel:
                    if localname(item.tag) != "item":
                        continue
                    
                    title = ""
                    link = ""
                    pub_date = None
                    
                    for elem in item:
                        tag = localname(elem.tag)
                        if tag == "title" and elem.text:
                            title = elem.text.strip()
                        elif tag == "link" and elem.text:
                            link = elem.text.strip()
                        elif tag == "pubDate" and elem.text:
                            pub_date = normalize_date(elem.text)
                    
                    if title and link:
                        items.append({
                            "title": title,
                            "link": link,
                            "published": pub_date or datetime.now(timezone.utc),
                            "source_page": feed_url
                        })
        
        # Handle Atom
        elif root_tag == "feed":
            for entry in root:
                if localname(entry.tag) != "entry":
                    continue
                
                title = ""
                link = ""
                pub_date = None
                
                for elem in entry:
                    tag = localname(elem.tag)
                    if tag == "title" and elem.text:
                        title = elem.text.strip()
                    elif tag == "link":
                        href = elem.get("href")
                        if href:
                            link = href.strip()
                    elif tag in ["published", "updated"] and elem.text:
                        pub_date = normalize_date(elem.text)
                
                if title and link:
                    items.append({
                        "title": title,
                        "link": link,
                        "published": pub_date or datetime.now(timezone.utc),
                        "source_page": feed_url
                    })
        
        print(f"[INFO] Parsed {len(items)} items from RSS feed: {feed_url}")
        
    except Exception as e:
        print(f"[WARN] Failed to parse RSS feed {feed_url}: {e}")
    
    return items


def select_relevant_urls(all_urls: List[str]) -> List[str]:
    """
    Filters URLs from the sitemap to relevant pages:
    - Domain help.zscaler.com
    - Contains hints for Release Notes or What's New
    - Excludes obvious non-articles
    """
    relevant: Set[str] = set()
    for u in all_urls:
        if not is_help_domain(u):
            continue
        path = urlparse(u).path.lower()
        if any(excl in path for excl in URL_EXCLUDE_HINTS):
            continue
        if any(hint in path for hint in URL_INCLUDE_HINTS):
            relevant.add(u)
    return sorted(relevant)


def normalize_date(date_text: Optional[str]) -> datetime:
    """
    Parse date string and normalize to UTC timezone.
    Returns current UTC time if parsing fails.
    Handles year transitions robustly by always using explicit year in parsed dates.
    """
    if not date_text:
        return datetime.now(timezone.utc)
    try:
        dt = dateparser.parse(date_text)
        if not dt:
            return datetime.now(timezone.utc)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def extract_date_from_soup(soup: BeautifulSoup) -> datetime:
    """
    Extract publication date from HTML page.
    Tries multiple strategies:
    1. Structured metadata (meta tags)
    2. HTML5 time element
    3. Visible date text
    
    Returns current UTC time as fallback.
    """
    # 1) Structured metadata
    meta_selectors = [
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="article:published_time"]', "content"),
        ('meta[property="og:updated_time"]', "content"),
        ('meta[name="date"]', "content"),
    ]
    for css, attr in meta_selectors:
        el = soup.select_one(css)
        if el and el.get(attr):
            return normalize_date(el.get(attr))

    # 2) time tag
    time_el = soup.find("time")
    if time_el:
        if time_el.get("datetime"):
            return normalize_date(time_el.get("datetime"))
        txt = time_el.get_text(strip=True)
        if txt:
            return normalize_date(txt)

    # 3) Visible date texts with explicit 4-digit year requirement
    for c in soup.select("*"):
        t = c.get_text(" ", strip=True)
        tl = t.lower()
        if any(k in tl for k in ["published", "updated", "release", "date", "released", "last updated"]):
            # Match date patterns that include 4-digit years:
            # - "31 December 2024" (day month year)
            # - "December 31, 2024" (month day, year)
            # - "2024-12-31" (ISO format)
            m = re.search(r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})", t)
            if m:
                return normalize_date(m.group(1))

    # Fallback: now
    return datetime.now(timezone.utc)


def extract_title(soup: BeautifulSoup, default: str) -> str:
    """
    Extract page title from HTML.
    Prefers H1, then <title>, then fallback.
    """
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return default


def build_feed(items: List[Dict]) -> bytes:
    """
    Build RSS feed from list of items.
    Each item should have: title, link, published, source_page
    """
    fg = FeedGenerator()
    fg.id(BASE)
    fg.title("Zscaler Releases (help.zscaler.com)")
    fg.link(href=BASE, rel='alternate')
    fg.link(href=urljoin(BASE, "/rss.xml"), rel='self')
    fg.description("Automatically generated feed for new Zscaler Release Notes across all products.")
    fg.language('en')

    items_sorted = sorted(items, key=lambda x: x["published"], reverse=True)
    for it in items_sorted:
        fe = fg.add_entry()
        fe.id(it["link"])
        fe.title(it["title"])
        fe.link(href=it["link"])
        fe.published(it["published"])
        fe.updated(it["published"])
        fe.summary(f"{it['title']} – Source: {it['source_page']}")
    return fg.rss_str(pretty=True)


def main():
    """
    Main function to generate RSS feed.
    
    Process:
    1. Read complete sitemap to understand site structure
    2. Discover RSS feeds from base URL and all subpages/sections
    3. Parse all discovered RSS feeds and aggregate items (parallel)
    4. If no RSS feeds found, fall back to page scraping (parallel)
    5. Apply time window filter (BACKFILL_DAYS)
    6. Deduplicate by link
    7. Build and write aggregated RSS feed
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    # 1) Read complete sitemap to understand site structure
    print("[INFO] Step 1: Reading sitemap to discover site structure...")
    all_urls = parse_sitemap(SITEMAP_URL)
    print(f"[INFO] Total URLs from sitemap: {len(all_urls)}")

    # 2) Discover RSS feeds from base URL and all subpages/sections
    print("[INFO] Step 2: Discovering RSS feeds from all subpages...")
    discovered_feeds = discover_rss_feeds(BASE, all_urls)
    print(f"[INFO] Total RSS feeds discovered: {len(discovered_feeds)}")
    
    aggregated: List[Dict] = []
    
    # 3) Parse all discovered RSS feeds (parallel)
    if discovered_feeds:
        print("[INFO] Step 3: Parsing discovered RSS feeds in parallel...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_feed = {
                executor.submit(parse_rss_feed, feed_url): feed_url
                for feed_url in discovered_feeds
            }
            for future in as_completed(future_to_feed):
                feed_url = future_to_feed[future]
                try:
                    items = future.result()
                    aggregated.extend(items)
                except Exception as e:
                    print(f"[WARN] Error parsing RSS feed {feed_url}: {e}")
        
        print(f"[INFO] Total items from RSS feeds: {len(aggregated)}")
    
    # 4) If no RSS feeds found or no items, fall back to page scraping (parallel)
    if not aggregated:
        print("[INFO] Step 4: No RSS feeds found or no items, falling back to page scraping...")
        candidates = select_relevant_urls(all_urls)
        print(f"[INFO] Relevant pages after filter: {len(candidates)}")
        for c in candidates[:15]:
            print(f" - {c}")
        if len(candidates) > 15:
            print(f" ... ({len(candidates) - 15} more)")
        
        def scrape_page(url: str) -> Optional[Dict]:
            """Scrape a single page for title and date."""
            try:
                html = fetch(url)
                soup = BeautifulSoup(html, "html.parser")
                title = extract_title(soup, default=url)
                published = extract_date_from_soup(soup)
                return {
                    "title": title,
                    "link": url,
                    "published": published,
                    "source_page": url
                }
            except Exception as e:
                print(f"[WARN] Error fetching: {url} -> {e}")
                return None
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(scrape_page, url): url for url in candidates}
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    if result:
                        aggregated.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    print(f"[WARN] Error processing page {url}: {e}")
        
        print(f"[INFO] Total items from page scraping: {len(aggregated)}")
    else:
        print("[INFO] Step 4: Skipping page scraping (RSS feeds provided sufficient data)")

    print(f"[INFO] Total extracted items: {len(aggregated)}")

    # 5) Apply time window
    window_items = [it for it in aggregated if it["published"] >= cutoff]
    print(f"[INFO] Step 5: Items within last {BACKFILL_DAYS} days: {len(window_items)}")

    # 6) Deduplicate by link
    final: List[Dict] = []
    seen = set()
    for it in window_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        final.append(it)
    
    print(f"[INFO] Step 6: Items after deduplication: {len(final)}")

    # 7) Build and write aggregated RSS
    rss_xml = build_feed(final)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    print(f"[INFO] Step 7: RSS written: {OUTPUT_PATH}")
    print(f"[INFO] Final feed contains {len(final)} items")


if __name__ == "__main__":
    main()
