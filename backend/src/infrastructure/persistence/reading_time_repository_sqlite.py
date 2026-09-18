"""Persistência dos tempos de avaliação humana em SQLite.

Um registro por avaliador (máx. 30), usado só nas métricas de eficiência.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.domain.validation import ReadingTimeEntry
from src.infrastructure.persistence.db_migrations import apply_migrations


class SQLiteReadingTimeRepository:
    """CRUD dos tempos únicos por avaliador."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reading_times (
                    entry_id TEXT PRIMARY KEY,
                    lawyer_name TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    evaluator_id TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, entry: ReadingTimeEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reading_times"
                " (entry_id, lawyer_name, minutes, created_at, evaluator_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    entry.entry_id,
                    entry.lawyer_name,
                    entry.minutes,
                    entry.created_at,
                    entry.evaluator_id,
                ),
            )

    def upsert(self, entry: ReadingTimeEntry) -> ReadingTimeEntry:
        """Cria ou atualiza o tempo do avaliador (unicidade por evaluator_id)."""
        if not entry.evaluator_id:
            self.save(entry)
            return entry
        existing = self.find_by_evaluator(entry.evaluator_id)
        if existing is None:
            self.save(entry)
            return entry
        self.update(
            existing.entry_id,
            entry.lawyer_name,
            entry.minutes,
            evaluator_id=entry.evaluator_id,
        )
        return ReadingTimeEntry(
            entry_id=existing.entry_id,
            lawyer_name=entry.lawyer_name,
            minutes=entry.minutes,
            created_at=existing.created_at,
            evaluator_id=entry.evaluator_id,
        )

    def get(self, entry_id: str) -> ReadingTimeEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_id, lawyer_name, minutes, created_at, evaluator_id"
                " FROM reading_times WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def find_by_evaluator(self, evaluator_id: str) -> ReadingTimeEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_id, lawyer_name, minutes, created_at, evaluator_id"
                " FROM reading_times WHERE evaluator_id = ?",
                (evaluator_id,),
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def update(
        self,
        entry_id: str,
        lawyer_name: str,
        minutes: int,
        *,
        evaluator_id: str | None = None,
    ) -> bool:
        with self._connect() as conn:
            if evaluator_id is not None:
                cursor = conn.execute(
                    "UPDATE reading_times SET lawyer_name = ?, minutes = ?, evaluator_id = ?"
                    " WHERE entry_id = ?",
                    (lawyer_name, int(minutes), evaluator_id, entry_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE reading_times SET lawyer_name = ?, minutes = ?"
                    " WHERE entry_id = ?",
                    (lawyer_name, int(minutes), entry_id),
                )
        return cursor.rowcount > 0

    def delete(self, entry_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM reading_times WHERE entry_id = ?", (entry_id,)
            )
        return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM reading_times").fetchone()
        return int(row["n"] if row else 0)

    def list_all(self) -> list[ReadingTimeEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry_id, lawyer_name, minutes, created_at, evaluator_id"
                " FROM reading_times ORDER BY lawyer_name ASC"
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> ReadingTimeEntry:
        evaluator_id = None
        try:
            raw = row["evaluator_id"]
            evaluator_id = str(raw) if raw else None
        except (KeyError, IndexError):
            evaluator_id = None
        return ReadingTimeEntry(
            entry_id=row["entry_id"],
            lawyer_name=row["lawyer_name"],
            minutes=int(row["minutes"]),
            created_at=row["created_at"],
            evaluator_id=evaluator_id,
        )
