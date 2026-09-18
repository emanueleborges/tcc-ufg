"""Persistência do cadastro de avaliadores (SQLite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.application.ports import EvaluatorRepositoryPort
from src.domain.validation import Evaluator
from src.infrastructure.persistence.db_migrations import apply_migrations


class SQLiteEvaluatorRepository(EvaluatorRepositoryPort):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_all(self) -> list[Evaluator]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT evaluator_id, name, sort_order FROM evaluators"
                " ORDER BY sort_order ASC, name ASC"
            ).fetchall()
        return [
            Evaluator(
                evaluator_id=row["evaluator_id"],
                name=row["name"],
                sort_order=int(row["sort_order"]),
            )
            for row in rows
        ]

    def get(self, evaluator_id: str) -> Evaluator | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT evaluator_id, name, sort_order FROM evaluators"
                " WHERE evaluator_id = ?",
                (evaluator_id,),
            ).fetchone()
        if row is None:
            return None
        return Evaluator(
            evaluator_id=row["evaluator_id"],
            name=row["name"],
            sort_order=int(row["sort_order"]),
        )
