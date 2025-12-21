#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator

This script collects Zscaler release notes from help.zscaler.com by:
- Using the complete sitemap (including sub-sitemaps and .xml.gz files)
- Filtering relevant pages (Release Notes & What's New) directly from the sitemap
- Extracting title & publication date from each page and creating an RSS feed
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

# Minimal pause between fetches (polite crawling)
FETCH_DELAY_SEC = 0.3


def fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
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
        for sm in root:
            if localname(sm.tag) != "sitemap":
                continue
            loc_el = next((c for c in sm if localname(c.tag) == "loc"), None)
            if loc_el is not None and loc_el.text:
                sub = loc_el.text.strip()
                urls.extend(parse_sitemap(sub))
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
    1. Read complete sitemap
    2. Select relevant pages (Release Notes & What's New)
    3. Fetch each candidate page and extract metadata
    4. Apply time window filter (BACKFILL_DAYS)
    5. Deduplicate by link
    6. Build and write RSS feed
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    # 1) Read complete sitemap
    all_urls = parse_sitemap(SITEMAP_URL)
    print(f"[INFO] Total URLs from sitemap: {len(all_urls)}")

    # 2) Select relevant pages (Release Notes & What's New)
    candidates = select_relevant_urls(all_urls)
    print(f"[INFO] Relevant pages after filter: {len(candidates)}")
    for c in candidates[:15]:
        print(f" - {c}")
    if len(candidates) > 15:
        print(f" ... ({len(candidates) - 15} more)")

    # 3) Fetch each candidate page and extract metadata
    aggregated: List[Dict] = []
    for url in candidates:
        try:
            html = fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            title = extract_title(soup, default=url)
            published = extract_date_from_soup(soup)
            aggregated.append({
                "title": title,
                "link": url,
                "published": published,
                "source_page": url
            })
            time.sleep(FETCH_DELAY_SEC)
        except Exception as e:
            print(f"[WARN] Error fetching: {url} -> {e}")

    print(f"[INFO] Total extracted pages: {len(aggregated)}")

    # 4) Apply time window
    window_items = [it for it in aggregated if it["published"] >= cutoff]
    print(f"[INFO] Within last {BACKFILL_DAYS} days: {len(window_items)}")

    # 5) Deduplicate by link
    final: List[Dict] = []
    seen = set()
    for it in window_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        final.append(it)

    # 6) Build and write RSS
    rss_xml = build_feed(final)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    print(f"[INFO] RSS written: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
