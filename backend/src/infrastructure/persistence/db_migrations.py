"""Migrações versionadas do SQLite de validações."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

from src.infrastructure.persistence.cohort_seed import EVALUATOR_NAMES

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

_PETITION_ID_RE = re.compile(r"^([0-9a-f]{12})_", re.IGNORECASE)


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Aplica migrações pendentes (idempotente)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    current = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    ).fetchone()[0]
    if current < 1:
        _migrate_v1(conn)
        _record(conn, 1)
        current = 1
    if current < 2:
        _migrate_v2(conn)
        _record(conn, 2)
        current = 2
    if current < 3:
        _migrate_v3(conn)
        _record(conn, 3)


def _record(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (version, datetime.now(timezone.utc).isoformat()),
    )


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Cria tabelas base se ainda não existirem (bootstrap)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS validations (
            validation_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS application_evaluations (
            entry_id TEXT PRIMARY KEY,
            petition_name TEXT NOT NULL,
            scores_json TEXT NOT NULL,
            problems_json TEXT NOT NULL DEFAULT '[]',
            injection_risk TEXT NOT NULL DEFAULT 'none',
            injection_score INTEGER NOT NULL DEFAULT 0,
            seconds REAL,
            created_at TEXT NOT NULL
        )
        """
    )


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Avaliadores fixos, petition_id nos snapshots e vínculo nas validações."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluators (
            evaluator_id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL
        )
        """
    )
    for index, name in enumerate(EVALUATOR_NAMES, start=1):
        evaluator_id = _stable_evaluator_id(name)
        conn.execute(
            "INSERT OR IGNORE INTO evaluators (evaluator_id, name, sort_order)"
            " VALUES (?, ?, ?)",
            (evaluator_id, name, index),
        )

    _ensure_column(conn, "application_evaluations", "petition_id", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_app_eval_petition
        ON application_evaluations(petition_id)
        WHERE petition_id IS NOT NULL AND petition_id != ''
        """
    )

    # Backfill petition_id a partir do nome do arquivo {id}_nome.pdf
    rows = conn.execute(
        "SELECT entry_id, petition_name, petition_id FROM application_evaluations"
    ).fetchall()
    for row in rows:
        if row["petition_id"]:
            continue
        match = _PETITION_ID_RE.match(str(row["petition_name"] or ""))
        if match:
            conn.execute(
                "UPDATE application_evaluations SET petition_id = ? WHERE entry_id = ?",
                (match.group(1).lower(), row["entry_id"]),
            )
        # Sem match: permanece NULL (legado não vinculado)

    _ensure_column(conn, "validations", "petition_id", "TEXT")
    _ensure_column(conn, "validations", "evaluator_id", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_validation_petition_evaluator
        ON validations(petition_id, evaluator_id)
        WHERE evaluator_id IS NOT NULL AND evaluator_id != ''
          AND petition_id IS NOT NULL AND petition_id != ''
        """
    )

    # Sincroniza colunas a partir do payload; NÃO associa avaliador automaticamente
    # aos registros seed-avaliacao-humana (permanecem legado sem evaluator_id).
    name_to_id = {
        row["name"]: row["evaluator_id"]
        for row in conn.execute("SELECT evaluator_id, name FROM evaluators")
    }
    for row in conn.execute(
        "SELECT validation_id, payload, petition_id, evaluator_id FROM validations"
    ):
        try:
            data = json.loads(row["payload"])
        except json.JSONDecodeError:
            continue
        petition_id = str(data.get("petition_id") or row["petition_id"] or "").strip()
        evaluator_id = data.get("evaluator_id") or row["evaluator_id"]
        # Legado seed: não vincula evaluator_id automaticamente
        if petition_id == "seed-avaliacao-humana":
            evaluator_id = None
            data["evaluator_id"] = None
        elif evaluator_id:
            evaluator_id = str(evaluator_id)
        else:
            evaluator_id = None
            data["evaluator_id"] = None

        # Atualiza payload se necessário e colunas denormalizadas
        payload = json.dumps(data, ensure_ascii=False)
        conn.execute(
            "UPDATE validations SET petition_id = ?, evaluator_id = ?, payload = ?"
            " WHERE validation_id = ?",
            (petition_id or None, evaluator_id, payload, row["validation_id"]),
        )

    logger.info(
        "Migração v2 aplicada: %d avaliadores cadastrados.",
        len(name_to_id),
    )


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """Tempo de avaliação: 1 registro por avaliador (máx. 30), com evaluator_id."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_times (
            entry_id TEXT PRIMARY KEY,
            lawyer_name TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    _ensure_column(conn, "reading_times", "evaluator_id", "TEXT")

    name_to_id = {
        str(row["name"]).strip().casefold(): (row["evaluator_id"], row["name"])
        for row in conn.execute("SELECT evaluator_id, name FROM evaluators")
    }

    by_name: dict[str, list[sqlite3.Row]] = {}
    for row in conn.execute(
        "SELECT entry_id, lawyer_name, minutes, created_at, evaluator_id"
        " FROM reading_times ORDER BY created_at DESC"
    ):
        key = str(row["lawyer_name"] or "").strip().casefold()
        by_name.setdefault(key, []).append(row)

    for key, group in by_name.items():
        mapped = name_to_id.get(key)
        if not mapped:
            for row in group:
                conn.execute(
                    "DELETE FROM reading_times WHERE entry_id = ?",
                    (row["entry_id"],),
                )
            continue
        evaluator_id, canonical_name = mapped
        minutes = round(sum(int(r["minutes"]) for r in group) / len(group))
        keep = group[0]
        conn.execute(
            "UPDATE reading_times SET lawyer_name = ?, minutes = ?, evaluator_id = ?"
            " WHERE entry_id = ?",
            (canonical_name, max(1, int(minutes)), evaluator_id, keep["entry_id"]),
        )
        for row in group[1:]:
            conn.execute(
                "DELETE FROM reading_times WHERE entry_id = ?",
                (row["entry_id"],),
            )

    # Garante no máximo um por evaluator_id
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_reading_time_evaluator
        ON reading_times(evaluator_id)
        WHERE evaluator_id IS NOT NULL AND evaluator_id != ''
        """
    )
    count = conn.execute("SELECT COUNT(*) FROM reading_times").fetchone()[0]
    logger.info("Migração v3 aplicada: %d tempos únicos por avaliador.", count)


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _stable_evaluator_id(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return f"ev-{digest[:10]}"
