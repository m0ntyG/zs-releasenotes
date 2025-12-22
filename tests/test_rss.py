#!/usr/bin/env python3
"""
Tests for RSS feed generation script.
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Add parent directory to path to import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_rss import (
    get_feed_urls,
    parse_rss_feed,
    build_feed,
    KNOWN_PRODUCTS
)

# Mock RSS feed content (RSS 2.0 format)
MOCK_RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>ZIA Release Notes</title>
    <link>https://help.zscaler.com/zia</link>
    <description>ZIA Release Notes</description>
    <item>
        <title>Enhanced Security Feature</title>
        <link>https://help.zscaler.com/zia/enhanced-security</link>
        <pubDate>Mon, 16 Dec 2024 10:00:00 +0000</pubDate>
        <guid>https://help.zscaler.com/zia/enhanced-security</guid>
        <description>New enhanced security feature for ZIA</description>
    </item>
    <item>
        <title>Performance Improvements</title>
        <link>https://help.zscaler.com/zia/performance</link>
        <pubDate>Fri, 13 Dec 2024 14:30:00 +0000</pubDate>
        <guid>https://help.zscaler.com/zia/performance</guid>
        <description>Performance improvements in ZIA</description>
    </item>
</channel>
</rss>
"""


def test_get_feed_urls():
    """Test that feed URLs are generated correctly for a given year."""
    feed_urls = get_feed_urls(2025)
    
    print(f"Generated {len(feed_urls)} feed URLs:")
    for url in sorted(feed_urls):
        print(f"  - {url}")
    
    # Should generate URLs for all known products
    assert len(feed_urls) == len(KNOWN_PRODUCTS), f"Expected {len(KNOWN_PRODUCTS)} feeds, found {len(feed_urls)}"
    
    # Check that URLs contain the year
    for url in feed_urls:
        assert "2025" in url, f"URL should contain year 2025: {url}"
    
    print("✓ test_get_feed_urls passed")


def test_parse_rss_feed():
    """Test that RSS feeds are correctly parsed."""
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.content = MOCK_RSS_FEED.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        items = parse_rss_feed("https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net")
        
        print(f"Parsed {len(items)} items:")
        for item in items:
            print(f"  - {item['title']}")
        
        # Should find 2 items from the mock feed
        assert len(items) == 2, f"Expected 2 items, found {len(items)}"
        
        # Check item details
        assert items[0]['title'] == "Enhanced Security Feature"
        assert items[0]['link'] == "https://help.zscaler.com/zia/enhanced-security"
        assert items[1]['title'] == "Performance Improvements"
        
    print("✓ test_parse_rss_feed passed")


def test_build_feed():
    """Test that the aggregated feed is correctly built."""
    
    # Sample items
    items = [
        {
            "title": "Test Item 1",
            "link": "https://help.zscaler.com/test1",
            "description": "Description for test item 1",
            "published": datetime(2024, 12, 20, 10, 0, 0, tzinfo=timezone.utc),
            "category": "Available"
        },
        {
            "title": "Test Item 2",
            "link": "https://help.zscaler.com/test2",
            "description": "Description for test item 2",
            "published": datetime(2024, 12, 19, 10, 0, 0, tzinfo=timezone.utc),
            "category": "Limited"
        }
    ]
    
    rss_xml = build_feed(items)
    rss_str = rss_xml.decode('utf-8')
    
    print("Generated RSS feed:")
    print(rss_str[:500] + "..." if len(rss_str) > 500 else rss_str)
    
    # Verify RSS structure
    assert b'<?xml version' in rss_xml
    assert b'<rss' in rss_xml
    assert b'<channel>' in rss_xml
    assert b'Zscaler Releases (help.zscaler.com)' in rss_xml
    assert b'Test Item 1' in rss_xml
    assert b'Test Item 2' in rss_xml
    
    print("✓ test_build_feed passed")


if __name__ == "__main__":
    print("Running RSS generation tests...\n")
    
    try:
        test_get_feed_urls()
        test_parse_rss_feed()
        test_build_feed()
        
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
