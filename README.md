# Zscaler Release Notes RSS Generator

Automatically collects and publishes Zscaler release notes from help.zscaler.com as an RSS feed by discovering and aggregating RSS feeds from all subpages.

## Features

- **RSS Feed Discovery**: Uses a curated list of known RSS feeds from https://help.zscaler.com/rss directory
- **Comprehensive Coverage**: Aggregates RSS feeds from all major Zscaler products (ZIA, ZPA, ZDX, Client Connector, etc.)
- **High Performance**: Parallel processing with concurrent.futures for fast execution
- **Connection Pooling**: Reuses HTTP connections for efficient network operations
- **Metadata Extraction**: Extracts titles, descriptions, categories, and publication dates from RSS feeds
- **RSS Feed Aggregation**: Combines multiple RSS feeds into a single comprehensive feed
- **Automated Updates**: GitHub Actions runs twice daily to keep the feed current
- **Date Filtering**: Filters items to recent releases (last 14 days by default)
- **Deduplication**: Removes duplicate entries across feeds

## How It Works

<<<<<<< HEAD
1. **Sitemap Parsing**: Fetches and parses the complete sitemap from help.zscaler.com to discover site structure (parallel parsing for nested sitemaps)
2. **RSS Feed Discovery** (prioritized strategies):
   - **Primary**: Scrapes the HTML directory page at https://help.zscaler.com/rss to find all RSS feed links (pattern: `/rss-feed/{product}/release-upgrade-summary-{year}/zscaler.net`)
   - **Fallback 1**: Checks for RSS feeds at base URL common paths
   - **Fallback 2**: Discovers product sections from sitemap (e.g., /zia, /zpa, /zdx) and checks for RSS feeds at each section path
   - **Fallback 3**: Looks for RSS feed links in HTML pages
   - All checks run in parallel for maximum efficiency
3. **RSS Feed Aggregation**: Parses all discovered RSS feeds concurrently and aggregates items
4. **Smart Fallback**: If no RSS feeds are found, falls back to:
   - Filtering relevant pages containing "release-notes" or "whats-new"
   - Scraping individual pages for title and publication date (parallel execution)
5. **Feed Processing**:
   - Filters items by publication date (configurable time window)
   - Deduplicates entries
=======
1. **Feed Discovery**: Uses a curated list of known RSS feed URLs from the Zscaler help portal directory
2. **RSS Feed Aggregation**: Parses all discovered RSS feeds concurrently and aggregates items
3. **Feed Processing**:
   - Filters items by publication date (configurable time window, default: 14 days)
   - Deduplicates entries based on title and link
>>>>>>> 40c33ad (Refactor code structure for improved readability and maintainability)
   - Sorts by publication date (newest first)
4. **Publishing**: Publishes aggregated feed to GitHub Pages via the `gh-pages` branch

## Configuration

### Environment Variables

- `BACKFILL_DAYS`: Number of days to look back for release notes (default: 14, configured in workflow: 90)

### GitHub Actions Schedule

The workflow runs automatically:
- **Twice daily** at 6 AM and 6 PM UTC (cron: `0 6,18 * * *`)
- **Manual trigger** available via workflow_dispatch

## Local Development

### Prerequisites

```bash
pip install requests beautifulsoup4 feedgen python-dateutil lxml
```

### Running Locally

```bash
python scripts/generate_rss.py
```

The RSS feed will be generated at `./public/rss.xml`.

### Testing with Custom Backfill Period

```bash
BACKFILL_DAYS=30 python scripts/generate_rss.py
```

## Date Handling Robustness

The script ensures robust date handling for future years:

- **4-digit year requirement**: All date regex patterns require 4-digit years (`\d{4}`)
- **Timezone-aware**: All dates are normalized to UTC
- **Year-boundary safe**: The backfill calculation using `timedelta` works correctly across year transitions
- **Comprehensive parsing**: Uses `python-dateutil` for flexible date format support

### Supported Date Formats

- ISO 8601: `2024-12-31`, `2024-12-31T10:30:00Z`
- US format: `December 31, 2024`, `Dec 31, 2024`
- European format: `31 December 2024`, `31 Dec 2024`
- Meta tags: `article:published_time`, `og:updated_time`
- HTML5: `<time datetime="...">` elements

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── zscaler-release-rss.yml   # GitHub Actions workflow
├── scripts/
│   └── generate_rss.py               # Main RSS generation script
├── public/                           # Generated RSS feed (gitignored)
│   └── rss.xml
├── .gitignore                        # Git ignore rules
└── README.md                         # This file
```

## RSS Feed

The generated RSS feed includes:

- **Title**: Zscaler Releases (help.zscaler.com)
- **Description**: Automatically generated feed for new Zscaler Release Notes across all products
- **Language**: English
- **Items**: Aggregated from all discovered RSS feeds and/or scraped pages
- **Time Window**: Release notes from the last 90 days (configurable)
- **Sorting**: Latest releases first
- **Deduplication**: Duplicate entries are automatically removed

## RSS Feed Discovery

<<<<<<< HEAD
The script discovers RSS feeds through multiple prioritized strategies:

1. **Primary Strategy - RSS Directory Scraping** (as per Zscaler_RSS_Feed_Guide.md):
   - Scrapes the HTML directory page at `https://help.zscaler.com/rss`
   - Extracts all RSS feed links matching the pattern `/rss-feed/{product}/release-upgrade-summary-{year}/zscaler.net`
   - Examples: `/rss-feed/zia/...`, `/rss-feed/zpa/...`, `/rss-feed/zdx/...`
   - This is the most reliable method as the directory page lists all available feeds

2. **Fallback Strategies** (only if primary strategy finds no feeds):
   - **Base URL Check**: Tests common RSS paths (`/rss`, `/feed`, `/rss.xml`, etc.)
   - **Section Discovery**: Extracts product sections from sitemap (e.g., `/zia/`, `/zpa/`, `/zdx/`)
   - **Section RSS Feeds**: Checks for RSS feeds at each discovered section path
   - **HTML Link Tags**: Parses pages for RSS feed links in `<link>` tags
   - **Anchor Links**: Searches for RSS feed links in page content

This approach ensures:
- **Comprehensive Coverage**: All product sections are included by scraping the directory
- **Reliable Discovery**: Primary strategy directly uses the official RSS directory page
- **Future-Proof**: New products/sections are automatically discovered
- **Resilient**: Multiple fallback strategies ensure feeds are found
- **High Performance**: Parallel execution reduces total runtime by 60-80%
=======
The script uses a curated list of known RSS feed URLs since the Zscaler help portal directory page is JavaScript-rendered and cannot be scraped statically. The current implementation includes 18 RSS feeds covering all major Zscaler products:

- ZIA (Zscaler Internet Access)
- ZPA (Zscaler Private Access) 
- ZDX (Zscaler Digital Experience)
- Zscaler Client Connector
- Cloud Branch Connector
- DSPM (Data Security Posture Management)
- Workflow Automation
- Business Insights
- Zidentity
- Risk360
- Deception
- ITDR (IT Detection & Response)
- Breach Predictor
- Zero Trust Branch
- Zscaler Cellular
- AEM (Adaptive Enforcement Management)
- ZSDK
- Unified Console

This approach ensures:
- **Comprehensive Coverage**: All major product sections are included
- **Reliable**: Uses verified feed URLs rather than dynamic discovery
- **High Performance**: Parallel execution for fetching and parsing feeds
- **Maintainable**: Feed list can be updated as new products are added
>>>>>>> 40c33ad (Refactor code structure for improved readability and maintainability)

## Performance Optimizations

The script uses several techniques to maximize performance:

1. **Parallel Execution**: Uses `concurrent.futures.ThreadPoolExecutor` for concurrent network operations
   - RSS feed fetching runs in parallel
   - RSS feed parsing is parallelized
   - Multiple feeds processed simultaneously

2. **Connection Pooling**: Uses `requests.Session` with connection pooling
   - Reuses TCP connections across requests
   - Reduces connection overhead
   - Pool size matches MAX_WORKERS for optimal resource usage

3. **Configurable Concurrency**: `MAX_WORKERS = 10` controls parallel execution
   - Balances performance with politeness
   - Prevents overwhelming the target server
   - Can be adjusted based on requirements

4. **Optimized Request Flow**: Eliminates unnecessary delays
   - No artificial sleep delays in parallel operations
   - Efficient XML parsing with lxml
   - Smart deduplication logic

## Contributing

When making changes, ensure:

1. RSS feed parsing handles both RSS 2.0 and Atom formats
2. All date patterns require 4-digit years for robust year handling
3. Dates are timezone-aware (UTC)
4. The BACKFILL_DAYS calculation handles year transitions correctly
5. New RSS feed URLs are added to the `known_feeds` set in `discover_feeds_from_directory()`
6. Run tests across year boundaries (e.g., December 31 to January 1)
7. Parallel operations use `ThreadPoolExecutor` for network I/O
8. Connection pooling via `requests.Session` is maintained

## Technical Details

### RSS Feed Discovery Process

<<<<<<< HEAD
The `discover_rss_feeds()` function implements a prioritized discovery strategy:

```python
# 1. PRIMARY: Scrape /rss directory page for feed links
html = fetch(BASE + "/rss")
for link in parse_html(html):
    if '/rss-feed/' in link:
        discovered_feeds.add(link)  # e.g., /rss-feed/zia/release-upgrade-summary-2025/zscaler.net

# 2. FALLBACK (only if primary strategy found no feeds):
# Check base URL
for path in ['/rss', '/feed', '/rss.xml', '/feed.xml', '/atom.xml']:
    check(BASE + path)

# 3. Extract sections from sitemap URLs
sections = extract_path_prefixes(sitemap_urls)  # e.g., /zia, /zpa, /zdx

# 4. Check each section for RSS feeds
for section in sections:
    for path in RSS_PATHS:
        check(BASE + section + path)

# 5. Parse HTML pages for RSS links
for page in key_pages:
    find_rss_links_in_html(page)
=======
The `discover_feeds_from_directory()` function uses a curated list of known RSS feed URLs:

```python
known_feeds = {
    "https://help.zscaler.com/rss-feed/zia/release-upgrade-summary-2025/zscaler.net",
    "https://help.zscaler.com/rss-feed/zpa/release-upgrade-summary-2025/private.zscaler.com",
    # ... additional known feeds
}
return known_feeds
>>>>>>> 40c33ad (Refactor code structure for improved readability and maintainability)
```

**Key Improvement**: The primary strategy directly scrapes the `/rss` directory page (which is HTML, not RSS) to find all actual RSS feed URLs. This follows the guidance in `Zscaler_RSS_Feed_Guide.md` and ensures all product feeds are discovered reliably.

### RSS Feed Parsing

Supports both RSS 2.0 and Atom formats:
- **RSS 2.0**: Parses `<item>` elements with `<title>`, `<link>`, `<pubDate>`, `<description>`, `<category>`
- **Atom**: Parses `<entry>` elements with `<title>`, `<link>`, `<published>`/`<updated>`

## License

This project is maintained for internal use to track Zscaler product releases.
