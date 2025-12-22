#!/usr/bin/env python3
"""
Tests for RSS feed generation script.
Uses mocking to simulate HTTP responses from help.zscaler.com.
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Add parent directory to path to import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.generate_rss import (
    discover_rss_feeds,
    parse_rss_feed,
    build_feed,
    normalize_date
)


# Mock HTML content for /rss directory page
MOCK_RSS_DIRECTORY_HTML = """
<!DOCTYPE html>
<html>
<head><title>RSS Feeds</title></head>
<body>
    <h1>Zscaler RSS Feeds</h1>
    <ul>
        <li><a href="/rss-feed/zia/release-upgrade-summary-2025/zscaler.net">ZIA RSS Feed</a></li>
        <li><a href="/rss-feed/zpa/release-upgrade-summary-2025/zscaler.net">ZPA RSS Feed</a></li>
        <li><a href="/rss-feed/experience-center/release-upgrade-summary-2025/zscaler.net">Experience Center RSS Feed</a></li>
        <li><a href="/rss-feed/zdx/release-upgrade-summary-2025/zscaler.net">ZDX RSS Feed</a></li>
    </ul>
</body>
</html>
"""

# Mock RSS feed content (RSS 2.0 format)
MOCK_RSS_FEED_ZIA = """<?xml version="1.0" encoding="UTF-8"?>
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

MOCK_RSS_FEED_ZPA = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>ZPA Release Notes</title>
    <link>https://help.zscaler.com/zpa</link>
    <description>ZPA Release Notes</description>
    <item>
        <title>New Access Policy</title>
        <link>https://help.zscaler.com/zpa/access-policy</link>
        <pubDate>Wed, 18 Dec 2024 09:00:00 +0000</pubDate>
        <guid>https://help.zscaler.com/zpa/access-policy</guid>
        <description>New access policy features in ZPA</description>
    </item>
</channel>
</rss>
"""


def test_discover_rss_feeds_from_directory():
    """Test that RSS feeds are discovered from the /rss directory page."""
    
    def mock_fetch(url, timeout=30):
        """Mock fetch function that returns appropriate content based on URL."""
        if url == "https://help.zscaler.com/rss":
            return MOCK_RSS_DIRECTORY_HTML
        elif "/rss-feed/zia/" in url:
            return MOCK_RSS_FEED_ZIA
        elif "/rss-feed/zpa/" in url:
            return MOCK_RSS_FEED_ZPA
        else:
            raise Exception(f"Unexpected URL: {url}")
    
    with patch('scripts.generate_rss.fetch', side_effect=mock_fetch):
        feeds = discover_rss_feeds("https://help.zscaler.com", [])
        
        print(f"Discovered {len(feeds)} feeds:")
        for feed in sorted(feeds):
            print(f"  - {feed}")
        
        # Should find 4 RSS feeds from the directory page
        assert len(feeds) >= 4, f"Expected at least 4 feeds, found {len(feeds)}"
        
        # Check for specific feeds
        assert any("/rss-feed/zia/" in feed for feed in feeds), "ZIA feed not found"
        assert any("/rss-feed/zpa/" in feed for feed in feeds), "ZPA feed not found"
        assert any("/rss-feed/experience-center/" in feed for feed in feeds), "Experience Center feed not found"
        assert any("/rss-feed/zdx/" in feed for feed in feeds), "ZDX feed not found"
    
    print("✓ test_discover_rss_feeds_from_directory passed")


def test_parse_rss_feed():
    """Test that RSS feeds are correctly parsed."""
    
    def mock_fetch(url, timeout=30):
        """Mock fetch function."""
        return MOCK_RSS_FEED_ZIA
    
    with patch('scripts.generate_rss.fetch', side_effect=mock_fetch):
        items = parse_rss_feed("https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net")
        
        print(f"Parsed {len(items)} items:")
        for item in items:
            print(f"  - {item['title']}")
        
        # Should find 2 items from ZIA feed
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
            "published": datetime(2024, 12, 20, 10, 0, 0, tzinfo=timezone.utc),
            "source_page": "https://help.zscaler.com/rss-feed/zia/test"
        },
        {
            "title": "Test Item 2",
            "link": "https://help.zscaler.com/test2",
            "published": datetime(2024, 12, 19, 10, 0, 0, tzinfo=timezone.utc),
            "source_page": "https://help.zscaler.com/rss-feed/zpa/test"
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


def test_normalize_date():
    """Test date normalization."""
    
    # Test RFC 2822 format
    date1 = normalize_date("Mon, 16 Dec 2024 10:00:00 +0000")
    assert date1.year == 2024
    assert date1.month == 12
    assert date1.day == 16
    
    # Test ISO format
    date2 = normalize_date("2024-12-16T10:00:00Z")
    assert date2.year == 2024
    assert date2.month == 12
    
    print("✓ test_normalize_date passed")


if __name__ == "__main__":
    print("Running RSS generation tests...\n")
    
    try:
        test_discover_rss_feeds_from_directory()
        test_parse_rss_feed()
        test_build_feed()
        test_normalize_date()
        
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
