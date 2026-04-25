"""Structured trace events — emit() never raises. Append-only in-process buffer
plus optional JSONL sink for post-run analysis.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class EventKind(StrEnum):
    WARMUP_COMPLETE = "warmup_complete"
    CONSOLIDATION_FIRED = "consolidation_fired"
    SMART_TRIGGER_DETECTED = "smart_trigger_detected"
    DISCOVERY_RANKED = "discovery_ranked"
    TIER_ATTEMPTED = "tier_attempted"
    TIER_WON = "tier_won"
    LLM_CALLED = "llm_called"
    PROFILE_UPDATED = "profile_updated"
    DRIFT_DETECTED = "drift_detected"
    CLUSTER_MATCHED = "cluster_matched"
    CRAWL_STARTED = "crawl_started"
    CRAWL_COMPLETED = "crawl_completed"
    CARRY_FORWARD = "carry_forward"
    DLQ_PUSH = "dlq_push"
    MERGE_INVOKED = "merge_invoked"
    EXTERNAL_RANK_INVOKED = "external_rank_invoked"
    DISCOVERY_LLM_INVOKED = "discovery_llm_invoked"


@dataclass
class TraceEvent:
    kind: EventKind
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    url: str = ""
    skill: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "timestamp": self.timestamp,
            "url": self.url,
            "skill": self.skill,
            "payload": self.payload,
        }


class _TraceSink:
    """In-process sink. Holds events in memory; optionally mirrors to a JSONL file."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self._jsonl_path: Path | None = None

    def configure_file(self, path: str | Path | None) -> None:
        self._jsonl_path = Path(path) if path else None
        if self._jsonl_path:
            try:
                self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:  # noqa: BLE001
                self._jsonl_path = None

    def write(self, event: TraceEvent) -> None:
        self.events.append(event)
        if self._jsonl_path is None:
            return
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception:  # noqa: BLE001
            # Sink must never raise into caller — silently drop the file mirror.
            pass

    def clear(self) -> None:
        self.events.clear()


_SINK = _TraceSink()


def emit(
    kind: EventKind | str,
    *,
    url: str = "",
    skill: str = "",
    **payload: Any,
) -> None:
    """Emit a trace event. Never raises."""
    try:
        if isinstance(kind, str):
            if kind in EventKind._value2member_map_:
                kind_enum = EventKind(kind)
            else:
                kind_enum = EventKind.LLM_CALLED
        else:
            kind_enum = kind
        event = TraceEvent(kind=kind_enum, url=url, skill=skill, payload=dict(payload))
        _SINK.write(event)
    except Exception:  # noqa: BLE001
        pass


def get_events() -> list[TraceEvent]:
    """Return a snapshot of buffered events (caller can iterate freely)."""
    return list(_SINK.events)


def configure_sink(path: str | Path | None) -> None:
    """Configure (or clear) the JSONL mirror file. Pass None to disable."""
    _SINK.configure_file(path)


def clear_events() -> None:
    """Clear the in-memory event buffer (does not truncate the JSONL mirror)."""
    _SINK.clear()
