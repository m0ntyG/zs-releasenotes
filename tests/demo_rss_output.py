#!/usr/bin/env python3
"""
Demonstration script showing how the RSS feed will look when it fetches real data.
This creates a sample RSS feed with mock data that resembles the actual output.
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from generate_rss import build_feed

# Create sample items that would come from aggregating multiple RSS feeds
today = datetime.now(timezone.utc)
yesterday = today - timedelta(days=1)
two_days_ago = today - timedelta(days=2)
three_days_ago = today - timedelta(days=3)

sample_items = [
    {
        "title": "ZIA: Enhanced Malware Protection",
        "link": "https://help.zscaler.com/zia/enhanced-malware-protection",
        "description": "New enhanced malware protection features for ZIA",
        "published": today,
        "category": "Available"
    },
    {
        "title": "ZPA: New App Connector Features",
        "link": "https://help.zscaler.com/zpa/new-app-connector",
        "description": "Improvements to App Connector functionality",
        "published": yesterday,
        "category": "Available"
    },
    {
        "title": "ZDX: Performance Monitoring Improvements",
        "link": "https://help.zscaler.com/zdx/performance-monitoring",
        "description": "Enhanced performance monitoring capabilities",
        "published": two_days_ago,
        "category": "Limited"
    },
    {
        "title": "Experience Center: Updated Dashboard",
        "link": "https://help.zscaler.com/experience-center/dashboard-update",
        "description": "New dashboard features and improvements",
        "published": three_days_ago,
        "category": "Available"
    }
]

# Build the RSS feed
rss_xml = build_feed(sample_items)

# Parse and pretty-print
root = ET.fromstring(rss_xml)
ET.indent(root, space='  ')
rss_str = ET.tostring(root, encoding='unicode')

print("=" * 80)
print("DEMONSTRATION: Expected RSS Feed Output")
print("=" * 80)
print("\nThis shows what the aggregated RSS feed will contain when the script")
print("successfully fetches and aggregates RSS feeds from help.zscaler.com/rss")
print("\n" + "=" * 80 + "\n")

print(rss_str)

print("\n" + "=" * 80)
print(f"\nKey Points:")
print(f"  ✓ Aggregates items from multiple product RSS feeds (ZIA, ZPA, ZDX, etc.)")
print(f"  ✓ Items are sorted by publication date (newest first)")
print(f"  ✓ Each item includes title, link, publication date, and source")
print(f"  ✓ Feed metadata includes proper RSS 2.0 structure")
print("=" * 80)
