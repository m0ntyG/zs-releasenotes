# Zscaler Release Notes RSS Generator

Automatically collects and publishes Zscaler release notes from help.zscaler.com as an RSS feed by discovering and aggregating RSS feeds from all subpages.

## Features

- **RSS Feed Discovery**: Automatically discovers RSS feeds from https://help.zscaler.com/rss and all product subpages
- **Comprehensive Coverage**: Aggregates RSS feeds from all sections (ZIA, ZPA, ZDX, etc.)
- **Future-Ready**: Automatically discovers new product sections and RSS feeds as they're added
- **Sitemap Parsing**: Uses sitemap to discover all sections for comprehensive RSS feed coverage
- **Smart Fallback**: Falls back to page scraping if RSS feeds are unavailable
- **Metadata Extraction**: Extracts titles and publication dates from RSS feeds and pages
- **RSS Feed Aggregation**: Combines multiple RSS feeds into a single comprehensive feed
- **Automated Updates**: GitHub Actions runs twice daily to keep the feed current
- **Year-Robust**: Date handling designed to work correctly across year transitions

## How It Works

1. **Sitemap Parsing**: Fetches and parses the complete sitemap from help.zscaler.com to discover site structure
2. **RSS Feed Discovery**: 
   - Checks for RSS feeds at base URL (https://help.zscaler.com/rss)
   - Discovers product sections from sitemap (e.g., /zia, /zpa, /zdx)
   - Checks for RSS feeds at each section path
   - Looks for RSS feed links in HTML pages
3. **RSS Feed Aggregation**: Parses all discovered RSS feeds and aggregates items
4. **Smart Fallback**: If no RSS feeds are found, falls back to:
   - Filtering relevant pages containing "release-notes" or "whats-new"
   - Scraping individual pages for title and publication date
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
- **Items**: Release notes from the last 90 days (configurable)
- **Sorting**: Latest releases first

## Contributing

When making changes to the date parsing logic, ensure:

1. All date patterns require 4-digit years
2. Dates are timezone-aware (UTC)
3. The BACKFILL_DAYS calculation handles year transitions correctly
4. Run tests across year boundaries (e.g., December 31 to January 1)

## License

This project is maintained for internal use to track Zscaler product releases.
