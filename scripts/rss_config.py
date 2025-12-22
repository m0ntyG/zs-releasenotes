"""
Configuration for Zscaler RSS feeds.

This file contains the known Zscaler products and their RSS feed configurations.
New products can be added here as they are released.
"""

from typing import Dict, List, Tuple

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

# Additional years to try if current year feeds are empty
FALLBACK_YEARS = [-1, 1]  # Try previous year, then next year

# Enable automatic discovery of new products from RSS directory
ENABLE_PRODUCT_DISCOVERY = True

# Maximum number of new products to discover per run
MAX_NEW_PRODUCTS_DISCOVERY = 5