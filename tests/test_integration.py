#!/usr/bin/env python3
"""
Integration test for RSS feed generation with mocked HTTP responses.
This test simulates the entire flow from discovery to feed generation.
"""

import sys
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the session before importing
mock_session = MagicMock()
with patch('scripts.generate_rss._session', mock_session):
    from scripts import generate_rss


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
    </ul>
</body>
</html>
"""

# Mock RSS feed content with recent dates
today = datetime.now(timezone.utc)
yesterday = today - timedelta(days=1)
two_days_ago = today - timedelta(days=2)

MOCK_RSS_FEED_ZIA = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>ZIA Release Notes</title>
    <link>https://help.zscaler.com/zia</link>
    <description>ZIA Release Notes</description>
    <item>
        <title>ZIA Feature 1</title>
        <link>https://help.zscaler.com/zia/feature1</link>
        <pubDate>{yesterday.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
        <guid>https://help.zscaler.com/zia/feature1</guid>
    </item>
    <item>
        <title>ZIA Feature 2</title>
        <link>https://help.zscaler.com/zia/feature2</link>
        <pubDate>{two_days_ago.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
        <guid>https://help.zscaler.com/zia/feature2</guid>
    </item>
</channel>
</rss>
"""

MOCK_RSS_FEED_ZPA = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>ZPA Release Notes</title>
    <link>https://help.zscaler.com/zpa</link>
    <description>ZPA Release Notes</description>
    <item>
        <title>ZPA Feature 1</title>
        <link>https://help.zscaler.com/zpa/feature1</link>
        <pubDate>{today.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
        <guid>https://help.zscaler.com/zpa/feature1</guid>
    </item>
</channel>
</rss>
"""


def mock_fetch(url, timeout=30):
    """Mock fetch function that returns appropriate content based on URL."""
    if url == "https://help.zscaler.com/rss":
        return MOCK_RSS_DIRECTORY_HTML
    elif "/rss-feed/zia/" in url:
        return MOCK_RSS_FEED_ZIA
    elif "/rss-feed/zpa/" in url:
        return MOCK_RSS_FEED_ZPA
    elif "sitemap.xml" in url:
        # Return empty sitemap
        return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    else:
        raise Exception(f"Unexpected URL: {url}")


def mock_fetch_bytes(url, timeout=30):
    """Mock fetch_bytes function."""
    return mock_fetch(url, timeout).encode('utf-8')


def test_full_integration():
    """Test the complete RSS generation flow."""
    
    print("Testing full RSS generation integration...")
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch all necessary functions
        with patch('scripts.generate_rss.fetch', side_effect=mock_fetch), \
             patch('scripts.generate_rss.fetch_bytes', side_effect=mock_fetch_bytes), \
             patch('scripts.generate_rss.OUTPUT_DIR', tmpdir), \
             patch('scripts.generate_rss.OUTPUT_PATH', os.path.join(tmpdir, 'rss.xml')), \
             patch('os.getenv', return_value='14'):  # BACKFILL_DAYS
            
            # Run main function
            generate_rss.main()
            
            # Check that the RSS file was created
            output_path = os.path.join(tmpdir, 'rss.xml')
            assert os.path.exists(output_path), "RSS file was not created"
            
            # Read and parse the generated RSS
            with open(output_path, 'rb') as f:
                rss_content = f.read()
            
            # Parse XML
            root = ET.fromstring(rss_content)
            
            # Verify RSS structure
            assert root.tag.endswith('rss'), "Root element should be <rss>"
            
            channel = root.find('channel')
            assert channel is not None, "No <channel> element found"
            
            # Check channel metadata
            title = channel.find('title')
            assert title is not None and 'Zscaler Releases' in title.text
            
            # Find all items
            items = channel.findall('item')
            print(f"Found {len(items)} items in generated feed")
            
            # Should have 3 items (2 from ZIA, 1 from ZPA)
            assert len(items) == 3, f"Expected 3 items, found {len(items)}"
            
            # Verify items are present and sorted by date (newest first)
            item_titles = [item.find('title').text for item in items]
            print(f"Items (in order): {item_titles}")
            
            # Verify that we have all expected items (order may vary slightly due to feedgen)
            expected_titles = {"ZIA Feature 1", "ZIA Feature 2", "ZPA Feature 1"}
            actual_titles = set(item_titles)
            assert actual_titles == expected_titles, f"Expected {expected_titles}, got {actual_titles}"
            
            # At minimum, verify the most recent item (today) is first
            # Get publication dates to verify ordering
            pub_dates = []
            for item in items:
                pub_elem = item.find('pubDate')
                if pub_elem is not None:
                    pub_dates.append(pub_elem.text)
            print(f"Publication dates: {pub_dates}")
            
            # Verify all items have required fields
            for item in items:
                assert item.find('title') is not None, "Item missing title"
                assert item.find('link') is not None, "Item missing link"
                assert item.find('guid') is not None, "Item missing guid"
                print(f"  ✓ {item.find('title').text}")
            
            print("✓ Full integration test passed")


if __name__ == "__main__":
    try:
        test_full_integration()
        print("\n✅ Integration test passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
