"""Persistência dos tempos reais de análise da aplicação (SQLite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.domain.validation import AnalysisTimeEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_times (
    entry_id TEXT PRIMARY KEY,
    petition_name TEXT NOT NULL,
    seconds REAL NOT NULL,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'auto'
)
"""


class SQLiteAnalysisTimeRepository:
    """CRUD dos tempos de análise automatizada."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, entry: AnalysisTimeEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO analysis_times"
                " (entry_id, petition_name, seconds, created_at, source)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    entry.entry_id,
                    entry.petition_name,
                    float(entry.seconds),
                    entry.created_at,
                    entry.source,
                ),
            )

    def list_all(self) -> list[AnalysisTimeEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry_id, petition_name, seconds, created_at, source"
                " FROM analysis_times ORDER BY created_at DESC"
            ).fetchall()
        return [
            AnalysisTimeEntry(
                entry_id=row["entry_id"],
                petition_name=row["petition_name"],
                seconds=float(row["seconds"]),
                created_at=row["created_at"],
                source=str(row["source"] or "auto"),
            )
            for row in rows
        ]

    def mean_seconds(self) -> float | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT AVG(seconds) AS mean_s, COUNT(*) AS n FROM analysis_times"
            ).fetchone()
        if row is None or int(row["n"] or 0) == 0:
            return None
        return float(row["mean_s"])
