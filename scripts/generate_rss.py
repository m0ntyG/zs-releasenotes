#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator

This script collects Zscaler release notes from help.zscaler.com by:
- Using a curated list of known RSS feed URLs for all products
- Parsing native RSS feeds from Zscaler's help site for all products and sections
- Aggregating items from all feeds into a single RSS feed
- Supporting automatic year updates and date filtering
- Optionally limiting the feed with BACKFILL_DAYS (default: 14, e.g., 90)

Requirements:
  uv sync
"""

import os
import re
import io
import gzip
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from dateutil import parser as dateparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib
import threading
import logging

# Import configuration
from rss_config import (
    KNOWN_PRODUCTS, FALLBACK_YEARS, ENABLE_PRODUCT_DISCOVERY,
    MAX_WORKERS, CACHE_FILE, LOG_LEVEL
)

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def normalize_date(date_str: str) -> datetime:
    """Normalize various date formats to a datetime object."""
    try:
        return dateparser.parse(date_str)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse date: {date_str}")
        return datetime.now()

BASE = "https://help.zscaler.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/2.0; +https://www.zscaler.com)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")
CACHE_DIR = os.path.join(os.getcwd(), ".cache")

MAX_WORKERS = MAX_WORKERS

# Exclusion patterns (to avoid obvious non-articles)
URL_EXCLUDE_HINTS = [
    "/tag/", "/taxonomy/", "/author/", "/search", "/attachment", "/node/",
]


def load_discovered_products_cache() -> Set[Tuple[str, str]]:
    """Load previously discovered products from cache."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                return set(tuple(product) for product in data.get('discovered_products', []))
        except Exception as e:
            logger.warning(f"Failed to load product cache: {e}")
    return set()


def save_discovered_products_cache(discovered_products: Set[Tuple[str, str]]):
    """Save discovered products to cache."""
    cache_dir = os.path.dirname(CACHE_FILE)
    os.makedirs(cache_dir, exist_ok=True)
    try:
        data = {
            'discovered_products': list(discovered_products),
            'last_updated': datetime.now().isoformat()
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save product cache: {e}")


def get_all_products() -> List[Tuple[str, str]]:
    """Get all products including known and previously discovered ones."""
    all_products = list(KNOWN_PRODUCTS)

    # Load cached discovered products
    cached_products = load_discovered_products_cache()
    all_products.extend(cached_products)

    return all_products


def discover_new_products() -> Set[Tuple[str, str]]:
    """
    Discover new Zscaler products by scraping the RSS directory page.
    Includes rate limiting, validation, and better error handling.
    """
    new_products = set()

    if not ENABLE_PRODUCT_DISCOVERY:
        logger.info("Product discovery is disabled")
        return new_products

    try:
        logger.info("Discovering new products from RSS directory...")

        # Add delay to be respectful to the server
        time.sleep(1)

        response = requests.get(f"{BASE}/rss", headers=HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Look for RSS feed links in the directory with multiple patterns
        feed_patterns = [
            r'/rss-feed/[^/]+/release-upgrade-summary-\d+/[^/]+',
            r'/rss-feed/[^/]+/release-notes-\d+/[^/]+',
            r'/feeds/[^/]+/release-\d+/[^/]+'
        ]

        discovered_links = set()

        for pattern in feed_patterns:
            feed_links = soup.find_all('a', href=re.compile(pattern))
            for link in feed_links:
                href = link.get('href', '').strip()
                if href and not href.startswith('http'):
                    href = BASE + href
                discovered_links.add(href)

        # Also look for links in RSS autodiscovery tags
        rss_links = soup.find_all('link', {'type': re.compile(r'application/(rss|atom)\+xml')})
        for link in rss_links:
            href = link.get('href', '').strip()
            if href and '/rss-feed/' in href:
                if not href.startswith('http'):
                    href = BASE + href
                discovered_links.add(href)

        known_product_slugs = {product for product, _ in get_all_products()}

        for href in discovered_links:
            # Try multiple regex patterns to extract product info
            patterns = [
                r'/rss-feed/([^/]+)/release-upgrade-summary-(\d+)/([^/]+)',
                r'/rss-feed/([^/]+)/release-notes-(\d+)/([^/]+)',
                r'/feeds/([^/]+)/release-(\d+)/([^/]+)'
            ]

            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    product_slug, year, domain = match.groups()
                    if product_slug not in known_product_slugs:
                        # Validate the product by checking if the feed URL exists
                        if validate_product_feed(product_slug, domain, year):
                            new_products.add((product_slug, domain))
                            logger.info(f"Discovered and validated new product: {product_slug} ({domain})")
                    break

        if new_products:
            logger.info(f"Successfully discovered {len(new_products)} new products")
            # Update cache with new discoveries
            existing_cache = load_discovered_products_cache()
            updated_cache = existing_cache.union(new_products)
            save_discovered_products_cache(updated_cache)
        else:
            logger.info("No new products discovered")

    except requests.RequestException as e:
        logger.warning(f"Network error during product discovery: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error during product discovery: {e}")

    return new_products


def validate_product_feed(product_slug: str, domain: str, year: str) -> bool:
    """
    Validate that a discovered product feed actually exists and returns valid RSS.
    """
    try:
        url = f"https://help.zscaler.com/rss-feed/{product_slug}/release-upgrade-summary-{year}/{domain}"
        response = requests.head(url, headers=HEADERS, timeout=5)

        if response.status_code == 200:
            # Do a quick content check to ensure it's actually RSS
            content_response = requests.get(url, headers=HEADERS, timeout=10)
            if content_response.status_code == 200:
                content = content_response.text.lower()
                if '<rss' in content or '<feed' in content:
                    return True

        return False
    except Exception:
        return False


def get_feed_urls_for_year(year: int) -> Set[str]:
    """
    Generate RSS feed URLs for a specific year using all known and discovered products.
    """
    feed_urls = set()
    products_to_check = get_all_products()

    # Add newly discovered products if enabled
    if ENABLE_PRODUCT_DISCOVERY:
        new_products = discover_new_products()
        products_to_check.extend(new_products)

    for product, domain in products_to_check:
        url = f"https://help.zscaler.com/rss-feed/{product}/release-upgrade-summary-{year}/{domain}"
        feed_urls.add(url)

    return feed_urls


def get_optimal_feed_urls() -> Set[str]:
    """
    Get RSS feed URLs with intelligent year selection and product discovery.
    Supports multiple years during transitions and automatic product discovery.
    """
    current_year = datetime.now().year
    years_to_check = [current_year]

    # Add fallback years if enabled
    if FALLBACK_YEARS:
        years_to_check.extend(current_year + offset for offset in FALLBACK_YEARS)

    # Remove duplicates and sort
    years_to_check = sorted(set(years_to_check))

    all_feed_urls = set()

    for year in years_to_check:
        logger.info(f"Checking RSS feeds for year {year}...")
        year_feed_urls = get_feed_urls_for_year(year)

        if year_feed_urls:
            # Quick validation: check if any feeds in this year are accessible
            sample_url = next(iter(year_feed_urls))
            try:
                response = requests.head(sample_url, headers=HEADERS, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Found active feeds for year {year} ({len(year_feed_urls)} feeds)")
                    all_feed_urls.update(year_feed_urls)
                    # If this is the current year and we found feeds, prioritize it
                    if year == current_year:
                        break
                else:
                    logger.info(f"No active feeds found for year {year} (HTTP {response.status_code})")
            except Exception as e:
                logger.info(f"Could not verify feeds for year {year}: {e}")
        else:
            logger.info(f"No feed URLs generated for year {year}")

    if not all_feed_urls:
        logger.warning("No active feeds found for any year, using current year as fallback")
        all_feed_urls = get_feed_urls_for_year(current_year)

    return all_feed_urls


def validate_feed_urls(feed_urls: Set[str]) -> Dict[str, bool]:
    """
    Validate which feed URLs are accessible and return their status.
    """
    validation_results = {}

    def check_feed(url):
        try:
            response = requests.head(url, headers=HEADERS, timeout=5)
            return url, response.status_code == 200
        except Exception:
            return url, False

    logger.info("Validating feed URLs...")
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(feed_urls))) as executor:
        futures = [executor.submit(check_feed, url) for url in feed_urls]
        for future in as_completed(futures):
            url, is_valid = future.result()
            validation_results[url] = is_valid

    valid_count = sum(validation_results.values())
    logger.info(f"Feed validation: {valid_count}/{len(feed_urls)} URLs are accessible")

    return validation_results


def get_known_feeds() -> Set[str]:
    """
    Return RSS feed URLs with automatic year selection and product discovery.
    Uses current year with fallback logic and discovers new products.
    """
    feed_urls = get_optimal_feed_urls()
    logger.info(f"Using {len(feed_urls)} RSS feeds")
    return feed_urls


def parse_rss_feed(feed_url: str) -> List[Dict]:
    """
    Parse an RSS or Atom feed and extract items.

    Returns a list of items with: title, link, published, source_page
    """
    items: List[Dict] = []
    try:
        response = requests.get(feed_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # Try to parse as RSS/Atom
        root = ET.fromstring(response.content)

        # Handle both RSS 2.0 and Atom formats
        if root.tag == 'rss':
            # RSS 2.0 format
            channel = root.find('channel')
            if channel is not None:
                for item_elem in channel.findall('item'):
                    item = parse_rss_item(item_elem, feed_url)
                    if item:
                        items.append(item)
        elif root.tag == '{http://www.w3.org/2005/Atom}feed':
            # Atom format
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                item = parse_atom_entry(entry, feed_url)
                if item:
                    items.append(item)

        logger.info(f"Parsed {len(items)} items from RSS feed: {feed_url}")

    except Exception as e:
        logger.error(f"Error parsing RSS feed {feed_url}: {e}")

    return items


def parse_rss_item(item_elem, source_url: str) -> Optional[Dict]:
    """Parse an RSS 2.0 item element."""
    try:
        title = item_elem.find('title')
        link = item_elem.find('link')
        description = item_elem.find('description')
        pub_date = item_elem.find('pubDate')
        category = item_elem.find('category')

        if title is None or link is None:
            return None

        # Extract text content
        title_text = title.text.strip() if title is not None and title.text else ""
        link_text = link.text.strip() if link is not None and link.text else ""
        desc_text = description.text.strip() if description is not None and description.text else ""
        category_text = category.text.strip() if category is not None and category.text else ""

        # Parse publication date
        published = None
        if pub_date is not None and pub_date.text:
            try:
                published = dateparser.parse(pub_date.text)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.warning(f"Could not parse date '{pub_date.text}': {e}")

        return {
            'title': title_text,
            'link': link_text,
            'description': desc_text,
            'published': published,
            'category': category_text,
            'source_page': source_url
        }
    except Exception as e:
        logger.error(f"Error parsing RSS item: {e}")
        return None


def parse_atom_entry(entry_elem, source_url: str) -> Optional[Dict]:
    """Parse an Atom entry element."""
    try:
        title = entry_elem.find('{http://www.w3.org/2005/Atom}title')
        link = entry_elem.find('{http://www.w3.org/2005/Atom}link')
        summary = entry_elem.find('{http://www.w3.org/2005/Atom}summary')
        content = entry_elem.find('{http://www.w3.org/2005/Atom}content')
        published = entry_elem.find('{http://www.w3.org/2005/Atom}published')
        updated = entry_elem.find('{http://www.w3.org/2005/Atom}updated')
        category = entry_elem.find('{http://www.w3.org/2005/Atom}category')

        if not title:
            return None

        # Extract title
        title_text = title.text.strip() if title.text else ""

        # Extract link
        link_href = ""
        if link is not None:
            link_href = link.get('href', '')

        # Extract description (prefer content over summary)
        desc_text = ""
        if content is not None and content.text:
            desc_text = content.text.strip()
        elif summary is not None and summary.text:
            desc_text = summary.text.strip()

        # Extract category
        category_text = ""
        if category is not None:
            category_text = category.get('term', '')

        # Parse publication date (prefer published over updated)
        published_date = None
        date_elem = published or updated
        if date_elem is not None and date_elem.text:
            try:
                published_date = dateparser.parse(date_elem.text)
                if published_date.tzinfo is None:
                    published_date = published_date.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.warning(f"Could not parse date '{date_elem.text}': {e}")

        return {
            'title': title_text,
            'link': link_href,
            'description': desc_text,
            'published': published_date,
            'category': category_text,
            'source_page': source_url
        }
    except Exception as e:
        logger.error(f"Error parsing Atom entry: {e}")
        return None


def build_feed(items: List[Dict]) -> bytes:
    """Build RSS feed from aggregated items."""
    fg = FeedGenerator()
    fg.title("Zscaler Releases (help.zscaler.com)")
    fg.description("Automatically generated feed for new Zscaler Release Notes across all products.")
    fg.link(href="https://help.zscaler.com/rss.xml", rel="self")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for item in items:
        fe = fg.add_entry()
        fe.title(item['title'])
        fe.link(href=item['link'])
        fe.description(item['description'])
        if item.get('published'):
            fe.pubDate(item['published'])
        if item.get('category'):
            fe.category(term=item['category'])

    return fg.rss_str(pretty=True)


def main():
    """
    Main function to generate RSS feed.

    Process:
    1. Get known RSS feed URLs for all Zscaler products
    2. Parse all RSS feeds and aggregate items (parallel)
    3. Apply time window filter (BACKFILL_DAYS)
    4. Deduplicate by link
    5. Build and write aggregated RSS feed
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)

    # 1) Get RSS feed URLs with year fallback and product discovery
    logger.info("Step 1: Getting RSS feed URLs with automatic discovery...")
    discovered_feeds = get_known_feeds()
    logger.info(f"Total RSS feeds: {len(discovered_feeds)}")

    # Optional: Validate feed URLs (can be disabled for performance)
    if os.getenv("VALIDATE_FEEDS", "false").lower() == "true":
        logger.info("Step 1.5: Validating feed URLs...")
        validation_results = validate_feed_urls(discovered_feeds)
        valid_feeds = {url for url, is_valid in validation_results.items() if is_valid}
        if len(valid_feeds) < len(discovered_feeds):
            logger.warning(f"Some feeds are not accessible: {len(discovered_feeds) - len(valid_feeds)} failed")
            discovered_feeds = valid_feeds

    aggregated: List[Dict] = []

    # 2) Parse all RSS feeds (parallel)
    logger.info("Step 2: Parsing RSS feeds in parallel...")

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
                logger.error(f"Error parsing RSS feed {feed_url}: {e}")

    logger.info(f"Total items from RSS feeds: {len(aggregated)}")

    # 3) Apply time window filter
    logger.info(f"Step 3: Filtering items within last {BACKFILL_DAYS} days...")
    filtered = [item for item in aggregated if item.get('published') and item['published'] > cutoff]
    logger.info(f"Items within time window: {len(filtered)}")

    # 4) Deduplicate by link
    logger.info("Step 4: Deduplicating by link...")
    seen_links = set()
    deduplicated = []
    for item in sorted(filtered, key=lambda x: x.get('published', datetime.min.replace(tzinfo=timezone.utc)), reverse=True):
        link = item.get('link', '')
        if link and link not in seen_links:
            seen_links.add(link)
            deduplicated.append(item)
    logger.info(f"Items after deduplication: {len(deduplicated)}")

    # 5) Build and write RSS feed
    logger.info("Step 5: Building and writing RSS feed...")
    rss_xml = build_feed(deduplicated)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    logger.info(f"RSS feed written to {OUTPUT_PATH}")
    logger.info(f"Final feed contains {len(deduplicated)} items")


if __name__ == "__main__":
    main()
