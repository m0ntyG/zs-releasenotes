# Zscaler Release Notes RSS Generator

Automatically collects and publishes Zscaler release notes from help.zscaler.com as an RSS feed by discovering and aggregating RSS feeds from all subpages.

## Features

- **RSS Feed Discovery**: Automatically discovers RSS feeds from https://help.zscaler.com/rss and all product subpages
- **Comprehensive Coverage**: Aggregates RSS feeds from all sections (ZIA, ZPA, ZDX, etc.)
- **Future-Ready**: Automatically discovers new product sections and RSS feeds as they're added
- **Sitemap Parsing**: Uses sitemap to discover all sections for comprehensive RSS feed coverage
- **High Performance**: Parallel processing with concurrent.futures for fast execution
- **Connection Pooling**: Reuses HTTP connections for efficient network operations
- **Smart Fallback**: Falls back to page scraping if RSS feeds are unavailable
- **Metadata Extraction**: Extracts titles and publication dates from RSS feeds and pages
- **RSS Feed Aggregation**: Combines multiple RSS feeds into a single comprehensive feed
- **Automated Updates**: GitHub Actions runs twice daily to keep the feed current
- **Year-Robust**: Date handling designed to work correctly across year transitions

## How It Works

1. **Sitemap Parsing**: Fetches and parses the complete sitemap from help.zscaler.com to discover site structure (parallel parsing for nested sitemaps)
2. **RSS Feed Discovery**: 
   - Checks for RSS feeds at base URL (https://help.zscaler.com/rss)
   - Discovers product sections from sitemap (e.g., /zia, /zpa, /zdx)
   - Checks for RSS feeds at each section path
   - Looks for RSS feed links in HTML pages
   - All checks run in parallel for maximum efficiency
3. **RSS Feed Aggregation**: Parses all discovered RSS feeds concurrently and aggregates items
4. **Smart Fallback**: If no RSS feeds are found, falls back to:
   - Filtering relevant pages containing "release-notes" or "whats-new"
   - Scraping individual pages for title and publication date (parallel execution)
5. **Feed Processing**:
   - Filters items by publication date (configurable time window)
   - Deduplicates entries
   - Sorts by publication date (newest first)
6. **Publishing**: Publishes aggregated feed to GitHub Pages via the `gh-pages` branch

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

The script discovers RSS feeds through multiple strategies:

1. **Base URL Check**: Tests common RSS paths (`/rss`, `/feed`, `/rss.xml`, etc.) at base URL
2. **Section Discovery**: Extracts product sections from sitemap (e.g., `/zia/`, `/zpa/`, `/zdx/`)
3. **Section RSS Feeds**: Checks for RSS feeds at each discovered section path
4. **HTML Link Tags**: Parses pages for RSS feed links in `<link>` tags
5. **Anchor Links**: Searches for RSS feed links in page content

This approach ensures:
- **Comprehensive Coverage**: All product sections are included
- **Future-Proof**: New sections are automatically discovered
- **Resilient**: Falls back to page scraping if RSS feeds are unavailable
- **High Performance**: Parallel execution reduces total runtime by 60-80%

## Performance Optimizations

The script uses several techniques to maximize performance:

1. **Parallel Execution**: Uses `concurrent.futures.ThreadPoolExecutor` for concurrent network operations
   - Nested sitemap parsing runs in parallel
   - RSS feed discovery checks run concurrently
   - RSS feed parsing is parallelized
   - Page scraping (fallback mode) runs in parallel

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
   - Single-pass RSS validation
   - Efficient content type checking

## Contributing

When making changes, ensure:

1. RSS feed discovery logic handles both RSS 2.0 and Atom formats
2. All date patterns require 4-digit years for robust year handling
3. Dates are timezone-aware (UTC)
4. The BACKFILL_DAYS calculation handles year transitions correctly
5. New RSS feed discovery strategies are added to `discover_rss_feeds()`
6. The fallback page scraping remains functional
7. Run tests across year boundaries (e.g., December 31 to January 1)
8. Parallel operations use `ThreadPoolExecutor` for network I/O
9. Connection pooling via `requests.Session` is maintained

## Technical Details

### RSS Feed Discovery Process

The `discover_rss_feeds()` function implements a comprehensive discovery strategy:

```python
# 1. Check base URL
for path in ['/rss', '/feed', '/rss.xml', '/feed.xml', '/atom.xml']:
    check(BASE + path)

# 2. Extract sections from sitemap URLs
sections = extract_path_prefixes(sitemap_urls)  # e.g., /zia, /zpa, /zdx

# 3. Check each section for RSS feeds
for section in sections:
    for path in RSS_PATHS:
        check(BASE + section + path)

# 4. Parse HTML pages for RSS links
for page in key_pages:
    find_rss_links_in_html(page)
```

### RSS Feed Parsing

Supports both RSS 2.0 and Atom formats:
- **RSS 2.0**: Parses `<item>` elements with `<title>`, `<link>`, `<pubDate>`
- **Atom**: Parses `<entry>` elements with `<title>`, `<link>`, `<published>`/`<updated>`

### Fallback Mechanism

If no RSS feeds are discovered or they contain no items:
1. Filters sitemap URLs for release notes and what's new pages
2. Scrapes each page for title and publication date
3. Uses the same aggregation and deduplication logic

## License

This project is maintained for internal use to track Zscaler product releases.
