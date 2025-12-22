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

### Step 1: Scrape Directory Page
To get all available feeds:
1. Fetch https://help.zscaler.com/rss
2. Parse the HTML to extract all RSS feed links
3. Links typically follow pattern: `/rss-feed/{product}/release-upgrade-summary-{year}/zscaler.net`

### Step 2: Fetch Individual Feeds
For each discovered feed URL:
1. Make HTTP GET request to the feed URL
2. Parse the XML response as RSS 2.0
3. Extract items and process as needed

### Step 3: Parse RSS Content
- Use XML parser to read RSS structure
- Handle HTML content in descriptions (may contain images, links, formatting)
- Convert pubDate to desired datetime format
- Extract relevant fields for your application

## Example Feed URLs
- ZIA: https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net
- Experience Center: https://help.zscaler.com/rss-feed/experience-center/release-upgrade-summary-2025/zscaler.net

## Notes
- Feeds contain release notes for 2025
- Content is updated regularly with new features and changes
- Some feeds may be empty or have limited items
- Rate limiting may apply for frequent requests
- Content includes HTML formatting that may need sanitization

## Implementation Considerations
- Cache feed responses to avoid excessive requests
- Handle network errors and timeouts gracefully
- Parse dates consistently across different locales
- Consider filtering by category or date ranges
- Store processed data in structured format (JSON, database, etc.)