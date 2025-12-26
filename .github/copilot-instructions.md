# Zscaler Release Notes RSS Generator - Copilot Instructions

## Overview
Python 3.12+ RSS aggregator that collects Zscaler release notes from help.zscaler.com, aggregating 18+ products (ZIA, ZPA, ZDX, etc.) across multiple years. Published to GitHub Pages twice daily via Actions.

**Stack:** Python 3.12+, uv package manager, feedgen, requests, BeautifulSoup | **Size:** ~18MB, 537 files

## Build, Test, Run

### Setup (Required First)
```bash
pip install uv  # CRITICAL: Always install uv first
uv sync         # Installs all dependencies (~30-45s, creates .venv)
```

### Generate RSS Feed
```bash
uv run python scripts/generate_rss.py              # Default: 14-day backfill
BACKFILL_DAYS=90 uv run python scripts/generate_rss.py  # Custom backfill
```
**Time:** ~5-8s | **Output:** `public/rss.xml` | **Process:** Discovers 4 years (2022-2026), validates 72 feeds, parses ~49 valid, filters/deduplicates, generates RSS 2.0

### Run Tests
```bash
uv run python tests/test_rss.py  # All 5 tests, ~5-8s, mocked HTTP
```

### Validate Output
```bash
[ -f public/rss.xml ] && grep -q "<channel>" public/rss.xml && echo "Valid" || echo "Invalid"
```

## Project Structure

```
├── .github/workflows/zscaler-release-rss.yml  # CI/CD (twice daily 6AM/6PM UTC)
├── scripts/
│   ├── generate_rss.py      # Main: discover_valid_years(), get_rss_feeds(), validate_feed_url(), 
│   │                        #       parse_rss_feed(), build_feed(), main() - ThreadPoolExecutor 10 workers
│   └── rss_config.py        # KNOWN_PRODUCTS (18), MAX_WORKERS (10)
├── tests/test_rss.py        # 5 unit tests, mocked HTTP
├── pyproject.toml           # Dependencies: requests, feedgen, beautifulsoup4, lxml, python-dateutil
└── uv.lock                  # Locked versions
```

## GitHub Actions CI/CD

**Workflow:** `.github/workflows/zscaler-release-rss.yml` | **Schedule:** Twice daily 6AM/6PM UTC + manual dispatch

**Steps:** Checkout → Setup Python 3.12 → `pip install uv` → `uv sync` (with cache) → `BACKFILL_DAYS=90 uv run python scripts/generate_rss.py` → Validate (check `public/rss.xml` exists + has `<channel>`, empty OK) → Deploy to `gh-pages`

## Common Tasks

**Add Product:** Edit `scripts/rss_config.py`, add `("product-slug", "domain.example.com")` to `KNOWN_PRODUCTS`, test with main script

**Change Backfill:** Set `BACKFILL_DAYS` env var or edit workflow `env.BACKFILL_DAYS`

**Debug:** Set `logging.basicConfig(level=logging.DEBUG)` in generate_rss.py | **Clean:** `rm -rf public/`

## Key Behaviors & Edge Cases

- **Year Discovery:** Discovers 2022-2026 via HEAD requests. New years auto-detected. No hardcoded values.
- **Feed Validation:** Pre-validates 72 URLs (18 products × 4 years) in parallel. Filters ~23 non-existent. Individual failures don't stop execution.
- **Dates:** UTC-normalized. ISO 8601, US, European formats supported. 4-digit years required (`\d{4}`). Works across year boundaries.
- **Empty Feeds:** Valid during quiet periods. Workflow accepts 0 `<item>` tags. Always generates valid RSS 2.0.
- **Parallel:** ThreadPoolExecutor, 10 workers, I/O-bound. No race conditions.
- **Output:** `public/` auto-created, gitignored (only in `gh-pages`).

## Code Modification Guidelines

**RSS Parsing:** MUST handle RSS 2.0 (`<item>`) and Atom (`<entry>`). Keep dates UTC. Require 4-digit years (`\d{4}`).

**Adding Products:** Update `KNOWN_PRODUCTS` in `scripts/rss_config.py`. Format: `("product-slug", "domain")`. Slug in URL: `https://help.zscaler.com/rss-feed/{slug}/release-upgrade-summary-{year}/{domain}`

**Parallel Processing:** Use ThreadPoolExecutor for I/O (not ProcessPoolExecutor). No shared state. Workers in `rss_config.MAX_WORKERS`.

**Testing:** Run `uv run python tests/test_rss.py` before commit. Add tests in `tests/test_rss.py`. Mock HTTP with `unittest.mock.patch`.

**No Linting Configured.** Follow existing style.

---

**Trust these instructions.** Only search if incomplete/incorrect. All commands verified.
