"""Persistência das validações humanas em SQLite.

Tabela ``validations`` com o payload completo em JSON (mesmo formato do
repositório legado em arquivos). Na primeira execução importa os JSONs
legados de ``validacoes/`` para o banco, sem perda de dados.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from src.application.ports import ValidationRepositoryPort
from src.domain.validation import HumanValidation
from src.infrastructure.persistence.validation_repository import (
    FileSystemValidationRepository,
    _from_dict,
    _to_dict,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS validations (
    validation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

DB_FILE_NAME = "validacoes.db"


class SQLiteValidationRepository(ValidationRepositoryPort):
    """Implementa ``ValidationRepositoryPort`` com SQLite (stdlib)."""

    def __init__(self, db_path: Path, legacy_dir: Path | None = None) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)
        if legacy_dir is not None:
            self._import_legacy(legacy_dir)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _import_legacy(self, legacy_dir: Path) -> None:
        legacy = FileSystemValidationRepository(legacy_dir)
        imported = 0
        with self._connect() as conn:
            for validation in legacy.list_all():
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO validations (validation_id, created_at, payload)"
                    " VALUES (?, ?, ?)",
                    (
                        validation.validation_id,
                        validation.created_at,
                        json.dumps(_to_dict(validation), ensure_ascii=False),
                    ),
                )
                imported += cursor.rowcount
        if imported:
            logger.info(
                "Validações legadas importadas para o SQLite: %d.", imported
            )

    def save(self, validation: HumanValidation) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO validations (validation_id, created_at, payload)"
                " VALUES (?, ?, ?)",
                (
                    validation.validation_id,
                    validation.created_at,
                    json.dumps(_to_dict(validation), ensure_ascii=False),
                ),
            )

    def get(self, validation_id: str) -> HumanValidation | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM validations WHERE validation_id = ?",
                (validation_id,),
            ).fetchone()
        if row is None:
            return None
        return _from_dict(json.loads(row["payload"]))

    def list_all(self) -> list[HumanValidation]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM validations ORDER BY created_at DESC"
            ).fetchall()
        items: list[HumanValidation] = []
        for row in rows:
            try:
                items.append(_from_dict(json.loads(row["payload"])))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return items
