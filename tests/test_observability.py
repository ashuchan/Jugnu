from __future__ import annotations

import json
from pathlib import Path

import pytest

from jugnu.observability.cost_ledger import CostLedger
from jugnu.observability.trace import (
    EventKind,
    clear_events,
    configure_sink,
    emit,
    get_events,
)


def test_emit_buffers_event_and_never_raises():
    clear_events()
    emit(EventKind.LLM_CALLED, url="https://x.com", skill="t", stage="prompt2", cost_usd=0.01)
    events = get_events()
    assert any(e.kind == EventKind.LLM_CALLED for e in events)
    # Bad payload still doesn't raise
    emit("nonexistent_kind", weird=object())  # type: ignore[arg-type]


def test_emit_writes_jsonl_when_configured(tmp_path: Path):
    clear_events()
    sink = tmp_path / "trace.jsonl"
    configure_sink(sink)
    try:
        emit(EventKind.WARMUP_COMPLETE, skill="news", memory_version=1)
        emit(EventKind.CRAWL_COMPLETED, skill="news", url_count=3)
    finally:
        configure_sink(None)
    assert sink.exists()
    lines = sink.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    parsed = [json.loads(l) for l in lines]
    assert parsed[0]["kind"] == str(EventKind.WARMUP_COMPLETE)
    assert parsed[1]["payload"]["url_count"] == 3


def test_cost_ledger_records_and_aggregates(tmp_path: Path):
    db = tmp_path / "cost.db"
    ledger = CostLedger(db)
    ledger.record(stage="prompt1", cost_usd=0.05, url="u1", skill="s", model="m")
    ledger.record(stage="prompt2", cost_usd=0.10, url="u1", skill="s", model="m")
    ledger.record(stage="prompt2", cost_usd=0.20, url="u2", skill="s", model="m2")
    assert db.exists()
    assert ledger.entry_count() == 3
    assert ledger.total_cost(skill="s") == pytest.approx(0.35)
    by_stage = ledger.cost_by_stage(skill="s")
    assert by_stage["prompt2"] == pytest.approx(0.30)
    by_url = ledger.cost_by_url(skill="s")
    assert by_url["u1"] == pytest.approx(0.15)
    by_model = ledger.cost_by_model(skill="s")
    assert by_model["m2"] == pytest.approx(0.20)


def test_cost_ledger_writes_to_disk_after_record(tmp_path: Path):
    db = tmp_path / "cost.db"
    ledger = CostLedger(db)
    ledger.record(stage="prompt5", cost_usd=0.001)
    # Re-open to confirm row was committed
    other = CostLedger(db)
    assert other.entry_count() == 1
