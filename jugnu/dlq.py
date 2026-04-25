from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class DlqEntry:
    url: str
    error: str
    attempt: int = 1
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    metadata: dict = field(default_factory=dict)


class DeadLetterQueue:
    """In-memory DLQ for failed crawl URLs."""

    def __init__(self, max_size: int = 1000) -> None:
        self._entries: list[DlqEntry] = []
        self._max = max_size

    def push(self, url: str, error: str, attempt: int = 1, metadata: dict | None = None) -> None:
        if len(self._entries) < self._max:
            self._entries.append(
                DlqEntry(url=url, error=error, attempt=attempt, metadata=metadata or {})
            )

    def pop_all(self) -> list[DlqEntry]:
        entries = self._entries[:]
        self._entries.clear()
        return entries

    def size(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return len(self._entries) == 0
