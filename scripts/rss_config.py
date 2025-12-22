"""
Configuration for Zscaler RSS feeds.

This file contains the known Zscaler products and their RSS feed configurations.
New products can be added here as they are released.
"""

from typing import Dict, List, Tuple
import os

# Known Zscaler products with their RSS feed configurations
# Format: (product_slug, domain)
KNOWN_PRODUCTS: List[Tuple[str, str]] = [
    ("zia", "zscaler.net"),
    ("zpa", "private.zscaler.com"),
    ("zdx", "zdxcloud.net"),
    ("zscaler-client-connector", "mobile.zscaler.net"),
    ("cloud-branch-connector", "connector.zscaler.net"),
    ("dspm", "app.zsdpc.net"),
    ("workflow-automation", "Zscaler-Automation"),
    ("business-insights", "zscaleranalytics.net"),
    ("zidentity", "zslogin.net"),
    ("risk360", "zscalerrisk.net"),
    ("deception", "illusionblack.com"),
    ("itdr", "illusionblack.com"),
    ("breach-predictor", "zscalerbp.net"),
    ("zero-trust-branch", "goairgap.com"),
    ("zscaler-cellular", "admin.ztsim.com"),
    ("aem", "app.avalor.io"),
    ("zsdk", "ZSDK"),
    ("unified", "console.zscaler.com"),
]

# Year handling configuration
# Additional years to try if current year feeds are empty
FALLBACK_YEARS = [-1, 1]  # Try previous year, then next year

# Enable support for multiple years simultaneously (useful during year transitions)
ENABLE_MULTI_YEAR_SUPPORT = True

# Maximum years to support simultaneously
MAX_CONCURRENT_YEARS = 2

# Product discovery configuration
# Enable automatic discovery of new products from RSS directory
ENABLE_PRODUCT_DISCOVERY = True

# Maximum number of new products to discover per run
MAX_NEW_PRODUCTS_DISCOVERY = 5

# Minimum days between discovery attempts to avoid spam
DISCOVERY_COOLDOWN_DAYS = 1

# Validation configuration
# Enable feed URL validation before processing
ENABLE_FEED_VALIDATION = os.getenv("VALIDATE_FEEDS", "false").lower() == "true"

# Timeout for feed validation (seconds)
FEED_VALIDATION_TIMEOUT = 5

# Performance configuration
# Maximum workers for parallel processing
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))

# Request timeout for RSS feed fetching
REQUEST_TIMEOUT = 30

# Cache configuration
# Enable caching of discovered products
ENABLE_CACHE = True

# Cache file location
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".cache", "discovered_products.json")

# Monitoring configuration
# Enable detailed logging
ENABLE_DETAILED_LOGGING = os.getenv("DETAILED_LOGGING", "false").lower() == "true"

# Log level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")