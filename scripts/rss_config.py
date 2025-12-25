"""
Configuration for Zscaler RSS feeds.

This file contains the known Zscaler products and their RSS feed configurations.
New products can be added here as they are released.

The RSS feed generator automatically discovers valid years for each product,
so no year configuration is needed. Years are dynamically detected by scanning
a range of years (default: 3 years back to 1 year forward) and validating
which ones have active RSS feeds.
"""

from typing import List, Tuple

# Known Zscaler products with their RSS feed configurations
# Format: (product_slug, domain)
# These products are automatically checked across all discovered years
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

# Maximum workers for parallel processing
MAX_WORKERS = 10
