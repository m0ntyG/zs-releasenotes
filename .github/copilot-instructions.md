# Zscaler Release Notes RSS Generator

## Overview
Aggregates Zscaler release notes from help.zscaler.com into a single RSS feed published via GitHub Pages. Key architecture: 3-stage parallel pipeline (year discovery → feed validation → RSS parsing).

## Core Files
- **`scripts/rss_config.py`**: Product list - add new Zscaler products here
- **`scripts/generate_rss.py`**: Main aggregator with parallel processing
- **`.github/workflows/zscaler-release-rss.yml`**: Runs twice daily, publishes to gh-pages

## Why This Architecture
- **Curated products**: Zscaler's RSS directory is React (not scrapable) → maintain list in `rss_config.py`
- **Parallel execution**: ~18 products × 4 years = 72+ feeds → ThreadPoolExecutor for I/O
- **Year discovery**: Auto-detects valid years via HTTP HEAD → no manual updates needed
- **HEAD validation**: Filters non-existent feeds before GET → avoids wasted requests

## Quick Start
```bash
uv sync                                      # Install (uses uv, not pip)
uv run python scripts/generate_rss.py        # Generate to ./public/rss.xml
BACKFILL_DAYS=90 uv run python scripts/generate_rss.py  # Custom window
uv run python tests/test_rss.py             # Run tests
```

## Critical Conventions

### Date Handling (REQUIRED)
- Year handling: Use integers from `datetime.now().year` (no regex/string parsing needed)
- Always timezone-aware UTC: `datetime.now(timezone.utc)`
- Use `dateparser.parse()` for flexibility (handles RFC 2822, ISO 8601, etc.)
- `timedelta` backfill works across year boundaries

### Adding Products
In `scripts/rss_config.py`:
```python
("product-slug", "domain.zscaler.com"),  # Generates: /rss-feed/{slug}/release-upgrade-summary-{year}/{domain}
```

### Parallel Pattern (for network I/O)
```python
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(fn, item): item for item in items}
    for future in as_completed(futures):
        result = future.result()
```

### RSS Formats
- RSS 2.0: `<item>` → `<pubDate>`, `<title>`, `<link>`, `<description>`
- Atom: `<entry>` → `<published>`, `<title>`, `<link href="">`, `<summary>`

## CI/GitHub Actions
- `BACKFILL_DAYS`: Default 14 (local), 90 (CI workflow)
- Feed must have `<channel>` but `<item>` count can be 0 (valid during quiet periods)
- Publishes to `gh-pages` branch with force orphan commits

## Common Workflows

**Add Zscaler product**: Add `("slug", "domain")` to `KNOWN_PRODUCTS` in `rss_config.py` (years auto-discover)

**Change time window**: Set `BACKFILL_DAYS` env var or update workflow YAML

**Debug failures**: Check logs for:
- "Found N valid year(s)" → year discovery
- "Found N valid RSS feeds" → validation filtering
- "Parsed N items" → successful parsing
- "Items within time window: N" → time filtering

## Key Constraints
- Python 3.12+ required
- Feed URL pattern: `/rss-feed/{product}/release-upgrade-summary-{year}/{domain}`
- Max 10 parallel workers (configurable in `rss_config.py`)
- Dependencies: uv (package manager), feedgen, python-dateutil, requests, beautifulsoup4, lxml
