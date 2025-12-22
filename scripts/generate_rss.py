#!/usr/bin/env python3
"""
Zscaler Help Releases RSS Generator

This script collects Zscaler release notes from help.zscaler.com by:
- Using a curated list of known RSS feed URLs for all products
- Parsing native RSS feeds from Zscaler's help site
- Aggregating items from all feeds into a single RSS feed
- Supporting automatic year transitions
- Filtering items by date (configurable with BACKFILL_DAYS)

Requirements:
  uv sync
"""

import os
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set
from xml.etree import ElementTree as ET
from feedgen.feed import FeedGenerator
from dateutil import parser as dateparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Import configuration
from rss_config import KNOWN_PRODUCTS, MAX_WORKERS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE = "https://help.zscaler.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Zscaler-Release-RSS/2.0; +https://www.zscaler.com)",
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"
}
OUTPUT_DIR = os.path.join(os.getcwd(), "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rss.xml")


def get_feed_urls(year: int) -> Set[str]:
    """Generate RSS feed URLs for a specific year using known products."""
    feed_urls = set()
    for product, domain in KNOWN_PRODUCTS:
        url = f"https://help.zscaler.com/rss-feed/{product}/release-upgrade-summary-{year}/{domain}"
        feed_urls.add(url)
    return feed_urls


def get_rss_feeds() -> Set[str]:
    """
    Get RSS feed URLs with automatic year selection.
    Tries current year first, then falls back to previous/next year if needed.
    """
    current_year = datetime.now().year
    
    # Try current year first
    logger.info(f"Checking RSS feeds for year {current_year}...")
    feed_urls = get_feed_urls(current_year)
    
    # Quick validation: check if any feeds are accessible
    sample_url = next(iter(feed_urls))
    try:
        response = requests.head(sample_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            logger.info(f"Found active feeds for year {current_year}")
            return feed_urls
    except Exception as e:
        logger.warning(f"Could not verify feeds for year {current_year}: {e}")
    
    # Try previous year as fallback
    logger.info(f"Trying previous year {current_year - 1}...")
    prev_year_urls = get_feed_urls(current_year - 1)
    sample_url = next(iter(prev_year_urls))
    try:
        response = requests.head(sample_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            logger.info(f"Found active feeds for year {current_year - 1}")
            return prev_year_urls
    except Exception as e:
        logger.warning(f"Could not verify feeds for year {current_year - 1}: {e}")
    
    # Try next year as fallback (useful in December/January)
    logger.info(f"Trying next year {current_year + 1}...")
    next_year_urls = get_feed_urls(current_year + 1)
    sample_url = next(iter(next_year_urls))
    try:
        response = requests.head(sample_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            logger.info(f"Found active feeds for year {current_year + 1}")
            return next_year_urls
    except Exception as e:
        logger.warning(f"Could not verify feeds for year {current_year + 1}: {e}")
    
    # Fallback to current year if all validations fail
    logger.warning("All year validations failed, using current year feeds")
    return feed_urls


def parse_rss_feed(feed_url: str) -> List[Dict]:
    """
    Parse an RSS or Atom feed and extract items.
    
    Returns a list of items with: title, link, description, published, category
    """
    items: List[Dict] = []
    try:
        response = requests.get(feed_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Parse as RSS/Atom
        root = ET.fromstring(response.content)
        
        # Handle both RSS 2.0 and Atom formats
        if root.tag == 'rss':
            # RSS 2.0 format
            channel = root.find('channel')
            if channel is not None:
                for item_elem in channel.findall('item'):
                    item = parse_rss_item(item_elem)
                    if item:
                        items.append(item)
        elif root.tag == '{http://www.w3.org/2005/Atom}feed':
            # Atom format
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                item = parse_atom_entry(entry)
                if item:
                    items.append(item)
        
        if items:
            logger.info(f"Parsed {len(items)} items from: {feed_url}")
    
    except Exception as e:
        logger.debug(f"Could not parse RSS feed {feed_url}: {e}")
    
    return items


def parse_rss_item(item_elem) -> Optional[Dict]:
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
            except Exception:
                pass
        
        return {
            'title': title_text,
            'link': link_text,
            'description': desc_text,
            'published': published,
            'category': category_text
        }
    except Exception:
        return None


def parse_atom_entry(entry_elem) -> Optional[Dict]:
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
            except Exception:
                pass
        
        return {
            'title': title_text,
            'link': link_href,
            'description': desc_text,
            'published': published_date,
            'category': category_text
        }
    except Exception:
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
    1. Get RSS feed URLs for current year (with fallback logic)
    2. Parse all RSS feeds and aggregate items (parallel)
    3. Apply time window filter (BACKFILL_DAYS)
    4. Deduplicate by link
    5. Sort by date and build aggregated RSS feed
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    BACKFILL_DAYS = int(os.getenv("BACKFILL_DAYS", "14"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)
    
    # 1) Get RSS feed URLs with year fallback
    logger.info("Step 1: Getting RSS feed URLs...")
    feed_urls = get_rss_feeds()
    logger.info(f"Using {len(feed_urls)} RSS feeds")
    
    # 2) Parse all RSS feeds (parallel)
    logger.info("Step 2: Parsing RSS feeds in parallel...")
    aggregated: List[Dict] = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_feed = {
            executor.submit(parse_rss_feed, feed_url): feed_url
            for feed_url in feed_urls
        }
        for future in as_completed(future_to_feed):
            try:
                items = future.result()
                aggregated.extend(items)
            except Exception as e:
                logger.error(f"Error parsing feed: {e}")
    
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
    logger.info("Step 5: Building RSS feed...")
    rss_xml = build_feed(deduplicated)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(rss_xml)
    logger.info(f"RSS feed written to {OUTPUT_PATH}")
    logger.info(f"Final feed contains {len(deduplicated)} items")


if __name__ == "__main__":
    main()
