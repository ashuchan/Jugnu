"""DLQ controller — policy layer over J2's DLQ primitive.

Decides retry schedule and parking rules. Keeps the DLQ data structure pure.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ..discovery.dlq import Dlq

log = logging.getLogger(__name__)


class DlqController:
    """Policy controller for the dead-letter queue.

    Args:
        dlq: The underlying DLQ data store.
        emit_fn: Event emission function.
    """

    def __init__(self, dlq: Dlq, emit_fn: Callable[..., Any]) -> None:
        self._dlq = dlq
        self._emit = emit_fn

    def schedule_retries_for(self, run_date: datetime | None = None) -> list[str]:
        """Get property IDs due for retry in this run."""
        if run_date is None:
            run_date = datetime.now(UTC)
        due = self._dlq.due_for_retry(run_date)
        ids = [e.property_id for e in due]
        for pid in ids:
            self._emit("discovery.dlq_retry_scheduled", pid)
        return ids

    def park_after_validation_failure(
        self,
        property_id: str,
        consecutive_unreachable: int,
        error_signature: str = "",
    ) -> bool:
        """Decide whether to park a property after repeated failures."""
        if consecutive_unreachable >= 3:
            self._dlq.park(property_id, "consecutive_unreachable", error_signature)
            self._emit("discovery.dlq_parked", property_id, reason="consecutive_unreachable")
            return True
        return False
