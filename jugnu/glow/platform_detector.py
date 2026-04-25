from __future__ import annotations

import re
from typing import Optional

_PLATFORM_SIGNATURES: dict[str, list[str]] = {
    "wordpress": ["wp-content", "wp-json", "wp-includes", "/wp/"],
    "shopify": ["cdn.shopify.com", "shopify.com/s/files", "Shopify.theme"],
    "wix": ["static.wixstatic.com", "wix-warmup-data"],
    "squarespace": ["squarespace.com", "squarespace-cdn"],
    "webflow": ["webflow.io", "webflow.com"],
    "nextjs": ["__NEXT_DATA__", "/_next/static"],
    "nuxtjs": ["__NUXT__", "/_nuxt/"],
    "drupal": ["drupal.org", "drupal.js", "/sites/default/files"],
    "joomla": ["/media/jui/", "joomla"],
    "magento": ["Mage.Cookies", "mage/", "/pub/static/"],
    "react": ["react-root", "__reactFiber", "__reactInternalInstance"],
    "angular": ["ng-version", "ng-app", "angular.json"],
    "vue": ["__vue_app__", "data-v-app"],
}


def detect_platform(html: str, url: str = "") -> Optional[str]:
    combined = (html + url).lower()
    for platform, signals in _PLATFORM_SIGNATURES.items():
        if any(sig.lower() in combined for sig in signals):
            return platform
    return None


def detect_platform_confidence(html: str, url: str = "") -> dict[str, float]:
    combined = (html + url).lower()
    scores: dict[str, float] = {}
    for platform, signals in _PLATFORM_SIGNATURES.items():
        hits = sum(1 for sig in signals if sig.lower() in combined)
        if hits:
            scores[platform] = hits / len(signals)
    return scores
