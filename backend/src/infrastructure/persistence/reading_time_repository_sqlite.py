"""Persistência dos tempos de leitura humana em SQLite.

Tabela ``reading_times`` no mesmo banco das validações
(``validacoes/validacoes.db``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.domain.validation import ReadingTimeEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reading_times (
    entry_id TEXT PRIMARY KEY,
    lawyer_name TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
"""


class SQLiteReadingTimeRepository:
    """CRUD simples dos registros de tempo de leitura (advogado + minutos)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, entry: ReadingTimeEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reading_times (entry_id, lawyer_name, minutes, created_at)"
                " VALUES (?, ?, ?, ?)",
                (entry.entry_id, entry.lawyer_name, entry.minutes, entry.created_at),
            )

    def get(self, entry_id: str) -> ReadingTimeEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_id, lawyer_name, minutes, created_at"
                " FROM reading_times WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        if row is None:
            return None
        return ReadingTimeEntry(
            entry_id=row["entry_id"],
            lawyer_name=row["lawyer_name"],
            minutes=int(row["minutes"]),
            created_at=row["created_at"],
        )

    def update(
        self, entry_id: str, lawyer_name: str, minutes: int
    ) -> bool:
        with self._connect() as conn:
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

    def list_all(self) -> list[ReadingTimeEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry_id, lawyer_name, minutes, created_at"
                " FROM reading_times ORDER BY created_at DESC"
            ).fetchall()
        return [
            ReadingTimeEntry(
                entry_id=row["entry_id"],
                lawyer_name=row["lawyer_name"],
                minutes=int(row["minutes"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
