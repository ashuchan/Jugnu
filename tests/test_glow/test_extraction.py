from __future__ import annotations

import json
import pytest

from jugnu.contracts import FetchResult
from jugnu.glow.platform_detector import detect_platform, detect_platform_confidence
from jugnu.glow.resolver import GlowResolver
from jugnu.glow.schema_normalizer import filter_to_schema, normalize_key, normalize_record
from jugnu.glow.tiers.tier1_json_ld import JsonLdAdapter
from jugnu.glow.tiers.tier2_api_json import ApiJsonAdapter
from jugnu.glow.tiers.tier3_microdata import MicrodataAdapter


JSON_LD_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "Product", "name": "Widget", "price": "9.99"}
</script>
</head><body></body></html>
"""

MICRODATA_HTML = """
<html><body>
<div itemscope itemtype="http://schema.org/Product">
  <span itemprop="name">Gadget</span>
  <span itemprop="price" content="19.99">$19.99</span>
</div>
</body></html>
"""


def test_platform_detector_wordpress():
    html = "<html><link rel='stylesheet' href='/wp-content/themes/theme.css'></html>"
    assert detect_platform(html) == "wordpress"


def test_platform_detector_nextjs():
    html = '<html><script id="__NEXT_DATA__" type="application/json">{}</script></html>'
    assert detect_platform(html) == "nextjs"


def test_platform_detector_unknown():
    html = "<html><body>Hello world</body></html>"
    assert detect_platform(html) is None


def test_platform_confidence_scores():
    html = "<html><link href='/wp-content/x.css'></html><script>wp-json</script>"
    scores = detect_platform_confidence(html)
    assert "wordpress" in scores


async def test_json_ld_adapter_extracts():
    fr = FetchResult(url="https://example.com", status_code=200, html=JSON_LD_HTML)
    adapter = JsonLdAdapter()
    assert await adapter.can_handle(fr) is True
    result = await adapter.extract(fr, ["name", "price"])
    assert len(result.records) == 1
    assert result.records[0]["name"] == "Widget"


async def test_api_json_adapter_list():
    data = json.dumps([{"title": "A"}, {"title": "B"}])
    fr = FetchResult(
        url="https://example.com/api/items",
        status_code=200,
        html=data,
        content_type="application/json",
    )
    adapter = ApiJsonAdapter()
    assert await adapter.can_handle(fr) is True
    result = await adapter.extract(fr, ["title"])
    assert len(result.records) == 2


async def test_microdata_adapter_extracts():
    fr = FetchResult(url="https://example.com", status_code=200, html=MICRODATA_HTML)
    adapter = MicrodataAdapter()
    assert await adapter.can_handle(fr) is True
    result = await adapter.extract(fr, ["name", "price"])
    assert len(result.records) == 1
    assert result.records[0]["name"] == "Gadget"


def test_normalize_key():
    assert normalize_key("Price USD") == "price_usd"
    assert normalize_key("item-name") == "item_name"


def test_normalize_record_with_alias():
    record = {"Property Title": "House"}
    aliases = {"title": ["Property Title", "name"]}
    normalized = normalize_record(record, aliases)
    assert "title" in normalized


async def test_glow_resolver_returns_adapter_result():
    fr = FetchResult(url="https://example.com", status_code=200, html=JSON_LD_HTML)
    resolver = GlowResolver()
    result = await resolver.resolve(fr, ["name", "price"])
    assert result.records is not None
    assert isinstance(result.tier_used, str)
