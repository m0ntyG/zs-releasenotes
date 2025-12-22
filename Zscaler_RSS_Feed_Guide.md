# Zscaler RSS Feed Retrieval Guide

## Overview
The Zscaler Help Portal provides RSS feeds for release notes and updates at https://help.zscaler.com/rss. However, the main `rss.xml` URL is empty and serves as a directory page with links to individual RSS feeds for different products and services.

## Structure
- **Main URL**: https://help.zscaler.com/rss - This is an HTML directory page, not an RSS feed.
- **Individual Feeds**: Links from the directory point to actual RSS feeds, e.g.:
  - ZIA (Zscaler Internet Access): https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net
  - Experience Center: https://help.zscaler.com/rss-feed/experience-center/release-upgrade-summary-2025/zscaler.net
  - Other products follow similar patterns

## Feed Format
Each RSS feed follows RSS 2.0 standard with:
- `<channel>` containing feed metadata (title, link, description)
- Multiple `<item>` elements, each representing a release note or update
- Each `<item>` contains:
  - `<title>`: Feature or update name
  - `<link>`: URL to detailed documentation
  - `<description>`: HTML-formatted description of the change
  - `<category>`: Availability status (Available, Limited, etc.)
  - `<pubDate>`: Publication date in RFC 2822 format
  - `<guid>`: Unique identifier

## Retrieval Process

### Step 1: Use Known Feed List
Since the directory page at https://help.zscaler.com/rss is a JavaScript-rendered React application, static HTML scraping cannot discover the feed URLs. Instead, use a curated list of known RSS feed URLs:

```python
known_feeds = {
    "https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net",
    "https://help.zscaler.com/rss-feed/zpa/release-upgrade-summary-2025/private.zscaler.com",
    "https://help.zscaler.com/rss-feed/zdx/release-upgrade-summary-2025/zdxcloud.net",
    # ... additional feeds
}
```

### Step 2: Fetch Individual Feeds
For each known feed URL:
1. Make HTTP GET request to the feed URL
2. Parse the XML response as RSS 2.0
3. Extract items and process as needed

### Step 3: Parse RSS Content
- Use XML parser to read RSS structure
- Handle HTML content in descriptions (may contain images, links, formatting)
- Convert pubDate to desired datetime format
- Extract relevant fields for your application

## Example Feed URLs
Here are the known RSS feed URLs for major Zscaler products (2025 releases):

- **ZIA (Zscaler Internet Access)**: https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net
- **ZPA (Zscaler Private Access)**: https://help.zscaler.com/rss-feed/zpa/release-upgrade-summary-2025/private.zscaler.com
- **ZDX (Zscaler Digital Experience)**: https://help.zscaler.com/rss-feed/zdx/release-upgrade-summary-2025/zdxcloud.net
- **Zscaler Client Connector**: https://help.zscaler.com/rss-feed/zscaler-client-connector/release-upgrade-summary-2025/mobile.zscaler.net
- **Cloud Branch Connector**: https://help.zscaler.com/rss-feed/cloud-branch-connector/release-upgrade-summary-2025/connector.zscaler.net
- **DSPM (Data Security Posture Management)**: https://help.zscaler.com/rss-feed/dspm/release-upgrade-summary-2025/app.zsdpc.net
- **Workflow Automation**: https://help.zscaler.com/rss-feed/workflow-automation/release-upgrade-summary-2025/Zscaler-Automation
- **Business Insights**: https://help.zscaler.com/rss-feed/business-insights/release-upgrade-summary-2025/zscaleranalytics.net
- **Zidentity**: https://help.zscaler.com/rss-feed/zidentity/release-upgrade-summary-2025/zslogin.net
- **Risk360**: https://help.zscaler.com/rss-feed/risk360/release-upgrade-summary-2025/zscalerrisk.net
- **Deception**: https://help.zscaler.com/rss-feed/deception/release-upgrade-summary-2025/illusionblack.com
- **ITDR (IT Detection & Response)**: https://help.zscaler.com/rss-feed/itdr/release-upgrade-summary-2025/illusionblack.com
- **Breach Predictor**: https://help.zscaler.com/rss-feed/breach-predictor/release-upgrade-summary-2025/zscalerbp.net
- **Zero Trust Branch**: https://help.zscaler.com/rss-feed/zero-trust-branch/release-upgrade-summary-2025/goairgap.com
- **Zscaler Cellular**: https://help.zscaler.com/rss-feed/zscaler-cellular/release-upgrade-summary-2025/admin.ztsim.com
- **AEM (Adaptive Enforcement Management)**: https://help.zscaler.com/rss-feed/aem/release-upgrade-summary-2025/app.avalor.io
- **ZSDK**: https://help.zscaler.com/rss-feed/zsdk/release-upgrade-summary-2025/ZSDK
- **Unified Console**: https://help.zscaler.com/rss-feed/unified/release-upgrade-summary-2025/console.zscaler.com

## Notes
- Feeds contain release notes for 2025
- Content is updated regularly with new features and changes
- Some feeds may be empty or have limited items
- Rate limiting may apply for frequent requests
- Content includes HTML formatting that may need sanitization

## Aggregation Implementation
The `scripts/generate_rss.py` script demonstrates a complete implementation that:

1. **Uses Known Feeds**: Maintains a curated list of 18 RSS feed URLs
2. **Parallel Processing**: Fetches and parses feeds concurrently for performance
3. **Date Filtering**: Filters items to recent releases (configurable, default 14 days)
4. **Deduplication**: Removes duplicate entries across feeds
5. **RSS Generation**: Creates a single aggregated RSS feed with all items
6. **Metadata Extraction**: Includes titles, descriptions, categories, and publication dates

### Running the Script
```bash
# Install uv package manager
pip install uv

# Install dependencies
uv sync

# Generate RSS feed
uv run python scripts/generate_rss.py

# Custom backfill period
BACKFILL_DAYS=30 uv run python scripts/generate_rss.py
```

The script outputs a comprehensive RSS feed at `public/rss.xml` containing aggregated release notes from all Zscaler products.