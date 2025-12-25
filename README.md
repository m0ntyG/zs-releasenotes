# Zscaler Release Notes RSS Generator

Automatically collects and publishes Zscaler release notes from help.zscaler.com as an RSS feed by discovering and aggregating RSS feeds from all subpages.

## Features

- **Curated Feed List**: Uses a maintained list of known RSS feeds from Zscaler help portal
- **Comprehensive Coverage**: Aggregates RSS feeds from all major Zscaler products (ZIA, ZPA, ZDX, Client Connector, etc.)
- **High Performance**: Parallel processing with ThreadPoolExecutor for fast execution
- **Automatic Year Discovery**: Automatically detects and aggregates feeds from multiple years (current and historical)
- **Smart Feed Validation**: Pre-validates RSS feed URLs to filter non-existent feeds before parsing
- **RSS Feed Aggregation**: Combines multiple RSS feeds into a single comprehensive feed
- **Automated Updates**: GitHub Actions runs twice daily to keep the feed current
- **Date Filtering**: Filters items to recent releases (last 14 days by default, configurable to 90)
- **Deduplication**: Removes duplicate entries across feeds
- **Resilient Processing**: Continues operation even if individual feeds fail

## How It Works

1. **Automatic Year Discovery**: Scans multiple years (up to 3 years back) in parallel to find all valid RSS feeds
2. **Feed URL Generation**: Generates RSS feed URLs for all discovered years and known products
3. **Parallel Validation**: Validates all feed URLs concurrently to filter out non-existent feeds
4. **RSS Feed Parsing**: Parses all valid RSS feeds in parallel and aggregates items
5. **Feed Processing**:
   - Filters items by publication date (configurable time window, default: 14 days)
   - Deduplicates entries based on link
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

## Automatic Year Discovery

The script automatically discovers and aggregates RSS feeds from multiple years:

- **Parallel Year Detection**: Scans years in parallel (default: 3 years back to 1 year forward) to identify which years have valid RSS feeds
- **Multi-Year Aggregation**: Automatically aggregates items from all discovered years
- **Zero Configuration**: No manual year updates needed - new years are automatically detected as they become available
- **Efficient Validation**: Pre-validates feeds using HTTP HEAD requests before parsing to avoid unnecessary processing
- **Resilient to Changes**: Gracefully handles year transitions and product additions/removals

## Date Handling Robustness

The script ensures robust date handling:

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
- **Future-Proof**: Automatically discovers valid years and adapts to new releases
- **High Performance**: Parallel execution for year discovery, validation, and parsing
- **Resilient**: Continues operation even if individual feeds fail
- **Maintainable**: Feed list can be updated as new products are added

## Performance Optimizations

The script uses several techniques to maximize performance and reliability:

1. **Parallel Execution**: Uses `concurrent.futures.ThreadPoolExecutor` for concurrent network operations
   - Year discovery runs in parallel (tests multiple years simultaneously)
   - Feed URL validation runs in parallel (filters non-existent feeds efficiently)
   - RSS feed parsing runs in parallel (multiple feeds processed simultaneously)
   - Configurable worker pool (default: 10 workers)

2. **Smart Validation**: Pre-validates feeds before parsing
   - HTTP HEAD requests to check feed existence (faster than GET)
   - Filters out non-existent feeds early to avoid wasted parsing attempts
   - Reduces unnecessary network traffic and processing time

3. **Efficient Processing**: Minimal overhead with optimized flow
   - Direct RSS parsing without intermediate caching
   - Early filtering of items outside time window
   - Straightforward error handling that doesn't halt execution

## Contributing

When making changes, ensure:

1. RSS feed parsing handles both RSS 2.0 and Atom formats
2. All date patterns require 4-digit years for robust year handling
3. Dates are timezone-aware (UTC)
4. The BACKFILL_DAYS calculation handles year transitions correctly
5. New RSS feed URLs are added to the `KNOWN_PRODUCTS` list in `rss_config.py`
6. Parallel operations use `ThreadPoolExecutor` for network I/O
7. Year discovery logic remains dynamic and doesn't hardcode year ranges
8. Code remains simple and maintainable

## Technical Details

### Automatic Year Discovery

The script uses a dynamic year discovery algorithm:

```python
# Discovers valid years by testing a range in parallel
valid_years = discover_valid_years(year_range=3)
# Example output: [2025, 2024, 2023, 2022]
```

- Tests years from (current - year_range) to (current + 1)
- Uses HTTP HEAD requests for fast validation
- Runs validation in parallel for efficiency
- Returns years sorted by recency (newest first)

### RSS Feed Generation

The script generates feed URLs for all known products across all discovered years:

```python
# For each valid year and product, generate feed URL
for year in valid_years:
    for product, domain in KNOWN_PRODUCTS:
        url = f"https://help.zscaler.com/rss-feed/{product}/release-upgrade-summary-{year}/{domain}"
```

**Multi-Year Aggregation**: The script automatically aggregates items from all discovered years, ensuring comprehensive coverage even during year transitions. Items are then filtered by the BACKFILL_DAYS time window.

### RSS Feed Parsing

Supports both RSS 2.0 and Atom formats:
- **RSS 2.0**: Parses `<item>` elements with `<title>`, `<link>`, `<pubDate>`, `<description>`, `<category>`
- **Atom**: Parses `<entry>` elements with `<title>`, `<link>`, `<published>`/`<updated>`

## License

This project is maintained for internal use to track Zscaler product releases.
