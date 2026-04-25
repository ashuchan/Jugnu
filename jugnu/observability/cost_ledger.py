"""SQLite cost ledger — per-URL, per-prompt-stage cost accumulation.

Records every LLM call with model, stage, tokens, cost. Read-side helpers expose
cost-by-stage / cost-by-url aggregations for run reports.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class CostLedger:
    """SQLite-backed ledger. Safe to instantiate multiple times against the same db file."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS cost_entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT NOT NULL,
        skill       TEXT NOT NULL DEFAULT '',
        url         TEXT NOT NULL DEFAULT '',
        stage       TEXT NOT NULL,
        model       TEXT NOT NULL DEFAULT '',
        input_tokens  INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        cost_usd    REAL NOT NULL DEFAULT 0.0
    );
    CREATE INDEX IF NOT EXISTS idx_cost_url   ON cost_entries(url);
    CREATE INDEX IF NOT EXISTS idx_cost_stage ON cost_entries(stage);
    CREATE INDEX IF NOT EXISTS idx_cost_skill ON cost_entries(skill);
    """

    def __init__(self, db_path: str | Path = "cost_ledger.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        *,
        stage: str,
        cost_usd: float,
        url: str = "",
        skill: str = "",
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Insert one cost row. Never raises — silently drops on DB error."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cost_entries
                        (timestamp, skill, url, stage, model, input_tokens, output_tokens, cost_usd)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        skill,
                        url,
                        stage,
                        model,
                        int(input_tokens or 0),
                        int(output_tokens or 0),
                        float(cost_usd or 0.0),
                    ),
                )
        except Exception:  # noqa: BLE001
            pass

    def total_cost(self, *, skill: str | None = None) -> float:
        sql = "SELECT COALESCE(SUM(cost_usd), 0.0) FROM cost_entries"
        params: tuple = ()
        if skill is not None:
            sql += " WHERE skill = ?"
            params = (skill,)
        try:
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
                return float(row[0]) if row else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    def cost_by_stage(self, *, skill: str | None = None) -> dict[str, float]:
        sql = "SELECT stage, SUM(cost_usd) FROM cost_entries"
        params: tuple = ()
        if skill is not None:
            sql += " WHERE skill = ?"
            params = (skill,)
        sql += " GROUP BY stage"
        try:
            with self._connect() as conn:
                return {row[0]: float(row[1] or 0.0) for row in conn.execute(sql, params)}
        except Exception:  # noqa: BLE001
            return {}

    def cost_by_url(self, *, skill: str | None = None) -> dict[str, float]:
        sql = "SELECT url, SUM(cost_usd) FROM cost_entries"
        params: tuple = ()
        if skill is not None:
            sql += " WHERE skill = ?"
            params = (skill,)
        sql += " GROUP BY url"
        try:
            with self._connect() as conn:
                return {row[0]: float(row[1] or 0.0) for row in conn.execute(sql, params)}
        except Exception:  # noqa: BLE001
            return {}

    def cost_by_model(self, *, skill: str | None = None) -> dict[str, float]:
        sql = "SELECT model, SUM(cost_usd) FROM cost_entries"
        params: tuple = ()
        if skill is not None:
            sql += " WHERE skill = ?"
            params = (skill,)
        sql += " GROUP BY model"
        try:
            with self._connect() as conn:
                return {row[0]: float(row[1] or 0.0) for row in conn.execute(sql, params)}
        except Exception:  # noqa: BLE001
            return {}

    def entry_count(self) -> int:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()
                return int(row[0]) if row else 0
        except Exception:  # noqa: BLE001
            return 0

    @property
    def db_path(self) -> Path:
        return self._db_path
