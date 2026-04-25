from __future__ import annotations

from jugnu.skill import OutputSchema
from jugnu.validation.cross_run_sanity import sanity_check
from jugnu.validation.identity_fallback import assign_identities
from jugnu.validation.schema_gate import passes_schema_gate


def test_schema_gate_passes():
    schema = OutputSchema(fields=["title", "price"], minimum_fields=["title"])
    records = [{"title": "Item 1", "price": "$10"}, {"title": "Item 2"}]
    passes, _ = passes_schema_gate(records, schema)
    assert passes is True


def test_schema_gate_fails_empty():
    schema = OutputSchema(fields=["title"], minimum_fields=["title"])
    passes, reason = passes_schema_gate([], schema)
    assert passes is False
    assert "no_records" in reason


def test_identity_fallback_assigns_id():
    records = [{"title": "A"}, {"title": "B"}]
    result = assign_identities(records)
    assert all("_id" in r for r in result)
    assert result[0]["_id"] != result[1]["_id"]


def test_cross_run_sanity_drop():
    old = [{"title": str(i)} for i in range(100)]
    new = [{"title": str(i)} for i in range(30)]
    passes, reason = sanity_check(new, old)
    assert passes is False
    assert "drop" in reason
