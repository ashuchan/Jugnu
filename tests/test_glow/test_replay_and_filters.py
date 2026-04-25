"""Coverage for the new replay + negative-keyword paths added during the
PropAi integration alignment work."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from jugnu.contracts import FetchResult
from jugnu.glow.schema_normalizer import (
    filter_records_by_negative_keywords,
    record_matches_negative_keyword,
)
from jugnu.glow.tiers.tier1_api import KnownApiAdapter
from jugnu.glow.tiers.tier1_profile import ProfileReplayAdapter
from jugnu.profile import ApiHints, LlmFieldMapping, ScrapeProfile
from jugnu.spark.crystallizer import crystallize


# ---------------------------------------------------------------------------
# Negative-keyword filtering
# ---------------------------------------------------------------------------


def test_record_matches_negative_keyword_substring():
    record = {"unit_id": "MODULE_left_nav", "rent": 1500}
    assert record_matches_negative_keyword(record, ["MODULE_"])


def test_record_matches_negative_keyword_nested_list():
    record = {"amenities": ["Pool", "Lease Magnet pop-up"]}
    assert record_matches_negative_keyword(record, ["Lease Magnet"])


def test_record_matches_negative_keyword_nested_dict():
    record = {"meta": {"source": "[Riedman]/inventory"}}
    assert record_matches_negative_keyword(record, ["[Riedman]"])


def test_filter_records_drops_only_matching():
    records = [
        {"unit_id": "101", "rent": 1500},
        {"unit_id": "MODULE_pricing", "rent": 1600},
        {"unit_id": "102", "rent": 1700},
    ]
    out = filter_records_by_negative_keywords(records, ["MODULE_"])
    assert [r["unit_id"] for r in out] == ["101", "102"]


def test_filter_records_no_keywords_passthrough():
    records = [{"x": 1}]
    assert filter_records_by_negative_keywords(records, None) == records
    assert filter_records_by_negative_keywords(records, []) == records


# ---------------------------------------------------------------------------
# Crystallizer writes per-mapping replay payload
# ---------------------------------------------------------------------------


def test_crystallize_populates_per_mapping_replay_fields():
    profile = ScrapeProfile(url_pattern="https://example.com")
    field_mappings = {
        "api": {
            "url_pattern": "/api/v1/units",
            "json_paths": {"rent": "pricing.monthly", "unit_id": "id"},
            "response_envelope": "data.units",
        },
        "dom": {
            "container": ".unit-list",
            "selectors": {"rent": ".price", "unit_id": ".unit-num"},
        },
    }
    crystallize(profile, field_mappings, field_mapping_notes="prompt2-discovery")

    by_field = {m.field_name: m for m in profile.field_mappings}
    rent = by_field["rent"]
    assert rent.api_url_pattern == "/api/v1/units"
    assert rent.json_paths == {"rent": "pricing.monthly", "unit_id": "id"}
    assert rent.response_envelope == "data.units"
    assert rent.dom_selector == ".price"
    assert rent.success_count == 0


# ---------------------------------------------------------------------------
# ProfileReplayAdapter — active API replay via httpx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_replay_active_api_walks_envelope_and_paths():
    profile = ScrapeProfile(url_pattern="https://prop.example.com/")
    profile.field_mappings = [
        LlmFieldMapping(
            field_name="rent",
            extraction_hint="pricing.monthly",
            api_url_pattern="/api/v1/units",
            json_paths={"rent": "pricing.monthly", "unit_id": "id"},
            response_envelope="data.units",
        ),
        LlmFieldMapping(
            field_name="unit_id",
            extraction_hint="id",
            api_url_pattern="/api/v1/units",
            json_paths={"rent": "pricing.monthly", "unit_id": "id"},
            response_envelope="data.units",
        ),
    ]

    payload = {
        "data": {
            "units": [
                {"id": "101", "pricing": {"monthly": 1500}},
                {"id": "102", "pricing": {"monthly": 1650}},
            ]
        }
    }
    fetch_result = FetchResult(
        url="https://prop.example.com/",
        status_code=200,
        html="<html></html>",  # Active replay does not need real HTML
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://prop.example.com/api/v1/units").mock(
            return_value=Response(200, json=payload)
        )
        adapter = ProfileReplayAdapter(profile=profile)
        result = await adapter.extract(fetch_result, ["rent", "unit_id"])

    assert len(result.records) == 2
    assert result.records[0]["rent"] == 1500
    assert result.records[0]["unit_id"] == "101"
    # success_count should have incremented for both fields.
    by_field = {m.field_name: m for m in profile.field_mappings}
    assert by_field["rent"].success_count == 1
    assert by_field["unit_id"].success_count == 1


@pytest.mark.asyncio
async def test_profile_replay_returns_empty_on_404_silently():
    profile = ScrapeProfile(url_pattern="https://prop.example.com/")
    profile.field_mappings = [
        LlmFieldMapping(
            field_name="rent",
            extraction_hint="rent",
            api_url_pattern="/api/v1/units",
            json_paths={"rent": "rent"},
        ),
    ]
    fetch_result = FetchResult(
        url="https://prop.example.com/",
        status_code=200,
        html="<html></html>",
    )
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://prop.example.com/api/v1/units").mock(
            return_value=Response(404)
        )
        adapter = ProfileReplayAdapter(profile=profile)
        result = await adapter.extract(fetch_result, ["rent"])
    assert result.records == []


# ---------------------------------------------------------------------------
# KnownApiAdapter honors per-URL blocked_endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_known_api_adapter_blocked_endpoint_short_circuits():
    fetch_result = FetchResult(
        url="https://example.com/api/v1/promotions",
        status_code=200,
        html='[{"unit_id": "101"}]',
        content_type="application/json",
    )
    adapter = KnownApiAdapter(
        learned_patterns=["/api/v1/"],
        blocked_endpoints=["/promotions"],
    )
    assert not await adapter.can_handle(fetch_result)


@pytest.mark.asyncio
async def test_known_api_adapter_unblocked_still_handles():
    fetch_result = FetchResult(
        url="https://example.com/api/v1/units",
        status_code=200,
        html='[{"unit_id": "101", "rent": 1500}]',
        content_type="application/json",
    )
    adapter = KnownApiAdapter(
        learned_patterns=["/api/v1/"],
        blocked_endpoints=["/promotions"],
    )
    assert await adapter.can_handle(fetch_result)
