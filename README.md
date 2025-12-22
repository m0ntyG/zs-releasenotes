# Zscaler Release Notes RSS Generator

Automatically collects and publishes Zscaler release notes from help.zscaler.com as an RSS feed by discovering and aggregating RSS feeds from all subpages.

## Features

- **Curated Feed List**: Uses a maintained list of known RSS feeds from Zscaler help portal
- **Comprehensive Coverage**: Aggregates RSS feeds from all major Zscaler products (ZIA, ZPA, ZDX, Client Connector, etc.)
- **High Performance**: Parallel processing with ThreadPoolExecutor for fast execution
- **Automatic Year Handling**: Intelligently switches between years during transitions
- **RSS Feed Aggregation**: Combines multiple RSS feeds into a single comprehensive feed
- **Automated Updates**: GitHub Actions runs twice daily to keep the feed current
- **Date Filtering**: Filters items to recent releases (last 14 days by default, configurable to 90)
- **Deduplication**: Removes duplicate entries across feeds

## How It Works

1. **Feed Discovery**: Uses a curated list of known RSS feed URLs from the Zscaler help portal
2. **RSS Feed Aggregation**: Parses all RSS feeds concurrently and aggregates items
3. **Feed Processing**:
   - Filters items by publication date (configurable time window, default: 14 days)
   - Deduplicates entries based on link
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
# Install uv package manager
pip install uv

# Install dependencies
uv sync
```

### Running Locally

```bash
uv run python scripts/generate_rss.py
```

The RSS feed will be generated at `./public/rss.xml`.

### Testing with Custom Backfill Period

```bash
BACKFILL_DAYS=30 uv run python scripts/generate_rss.py
```

## Date Handling Robustness

The script ensures robust date handling for future years:

- **Automatic Year Switching**: Automatically tries current year, then falls back to previous/next year
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

The script uses a curated list of known RSS feed URLs covering all major Zscaler products:

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
- **Future-Proof**: Automatically tries current year and fallback years
- **High Performance**: Parallel execution for fetching and parsing feeds
- **Maintainable**: Feed list can be updated as new products are added

## Performance Optimizations

The script uses several techniques to maximize performance:

1. **Parallel Execution**: Uses `concurrent.futures.ThreadPoolExecutor` for concurrent network operations
   - RSS feed fetching runs in parallel
   - Multiple feeds processed simultaneously
   - Configurable worker pool (default: 10 workers)

2. **Simple and Efficient**: Minimal overhead with direct RSS parsing
   - No caching complexity
   - No unnecessary validation steps
   - Straightforward error handling

## Contributing

When making changes, ensure:

1. RSS feed parsing handles both RSS 2.0 and Atom formats
2. All date patterns require 4-digit years for robust year handling
3. Dates are timezone-aware (UTC)
4. The BACKFILL_DAYS calculation handles year transitions correctly
5. New RSS feed URLs are added to the `KNOWN_PRODUCTS` list in `rss_config.py`
6. Parallel operations use `ThreadPoolExecutor` for network I/O
7. Code remains simple and maintainable

## Technical Details

### RSS Feed Generation

The script generates feed URLs for all known products with automatic year handling:

```python
# For each product, generate feed URL with current year
for product, domain in KNOWN_PRODUCTS:
    url = f"https://help.zscaler.com/rss-feed/{product}/release-upgrade-summary-{year}/{domain}"
```

**Year Handling**: The script tries the current year first, and if no feeds are found, falls back to previous or next year. This ensures the feed continues working during year transitions.

### RSS Feed Parsing

Supports both RSS 2.0 and Atom formats:
- **RSS 2.0**: Parses `<item>` elements with `<title>`, `<link>`, `<pubDate>`, `<description>`, `<category>`
- **Atom**: Parses `<entry>` elements with `<title>`, `<link>`, `<published>`/`<updated>`

## License

This project is maintained for internal use to track Zscaler product releases.
