"""Persistência dos snapshots de avaliação da aplicação (SQLite)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.application.ports import ApplicationEvaluationRepositoryPort
from src.domain.validation import ApplicationEvaluationEntry
from src.infrastructure.persistence.db_migrations import apply_migrations

_SCORE_KEYS = (
    "estrutura",
    "clareza",
    "coerencia",
    "fundamentacao",
    "consistencia",
    "elementos_essenciais",
    "geral",
)


def scores_to_percent(scores: dict[str, float]) -> dict[str, float]:
    """Normaliza scores 0–10 → 0–100%; valores já em % permanecem."""
    out: dict[str, float] = {}
    for key in _SCORE_KEYS:
        if key not in scores:
            continue
        value = float(scores[key] or 0.0)
        out[key] = round(value * 10.0, 1) if value <= 10.0 else round(value, 1)
    return out


class SQLiteApplicationEvaluationRepository(ApplicationEvaluationRepositoryPort):
    """CRUD dos snapshots de notas da aplicação."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert(self, entry: ApplicationEvaluationEntry) -> None:
        """Cria ou atualiza o snapshot atual da petição (reanálise)."""
        with self._connect() as conn:
            if entry.petition_id:
                existing = conn.execute(
                    "SELECT entry_id FROM application_evaluations"
                    " WHERE petition_id = ?",
                    (entry.petition_id,),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE application_evaluations SET"
                        " petition_name = ?, scores_json = ?, problems_json = ?,"
                        " injection_risk = ?, injection_score = ?, seconds = ?,"
                        " created_at = ?, petition_id = ?"
                        " WHERE entry_id = ?",
                        (
                            entry.petition_name,
                            json.dumps(entry.scores, ensure_ascii=False),
                            json.dumps(entry.problems, ensure_ascii=False),
                            entry.injection_risk,
                            int(entry.injection_score),
                            entry.seconds,
                            entry.created_at,
                            entry.petition_id,
                            existing["entry_id"],
                        ),
                    )
                    return
            conn.execute(
                "INSERT INTO application_evaluations"
                " (entry_id, petition_name, scores_json, problems_json,"
                "  injection_risk, injection_score, seconds, created_at, petition_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.entry_id,
                    entry.petition_name,
                    json.dumps(entry.scores, ensure_ascii=False),
                    json.dumps(entry.problems, ensure_ascii=False),
                    entry.injection_risk,
                    int(entry.injection_score),
                    entry.seconds,
                    entry.created_at,
                    entry.petition_id,
                ),
            )

    def save(self, entry: ApplicationEvaluationEntry) -> None:
        """Compat: delega para upsert."""
        self.upsert(entry)

    def get_by_petition_id(
        self, petition_id: str
    ) -> ApplicationEvaluationEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entry_id, petition_name, scores_json, problems_json,"
                " injection_risk, injection_score, seconds, created_at, petition_id"
                " FROM application_evaluations WHERE petition_id = ?",
                (petition_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def list_all(self) -> list[ApplicationEvaluationEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry_id, petition_name, scores_json, problems_json,"
                " injection_risk, injection_score, seconds, created_at, petition_id"
                " FROM application_evaluations ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def list_linked(self) -> list[ApplicationEvaluationEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry_id, petition_name, scores_json, problems_json,"
                " injection_risk, injection_score, seconds, created_at, petition_id"
                " FROM application_evaluations"
                " WHERE petition_id IS NOT NULL AND petition_id != ''"
                " ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def mean_scores(
        self, *, petition_id: str | None = None
    ) -> dict[str, float] | None:
        if petition_id:
            item = self.get_by_petition_id(petition_id)
            items = [item] if item else []
        else:
            items = self.list_linked()
        if not items:
            return None
        means: dict[str, float] = {}
        for key in _SCORE_KEYS:
            values = [
                float(item.scores[key])
                for item in items
                if key in item.scores and item.scores[key] is not None
            ]
            if values:
                means[key] = round(sum(values) / len(values))
        return means or None

    def delete_by_petition_id(self, petition_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM application_evaluations WHERE petition_id = ?",
                (petition_id,),
            )
        return cursor.rowcount > 0

    def _row_to_entry(self, row: sqlite3.Row) -> ApplicationEvaluationEntry:
        try:
            scores = json.loads(row["scores_json"] or "{}")
            problems = json.loads(row["problems_json"] or "[]")
        except json.JSONDecodeError:
            scores, problems = {}, []
        petition_id = row["petition_id"] if "petition_id" in row.keys() else None
        return ApplicationEvaluationEntry(
            entry_id=row["entry_id"],
            petition_name=row["petition_name"],
            scores={k: float(v) for k, v in dict(scores).items()},
            problems=[str(p) for p in list(problems)],
            injection_risk=str(row["injection_risk"] or "none"),
            injection_score=int(row["injection_score"] or 0),
            created_at=row["created_at"],
            seconds=(
                float(row["seconds"]) if row["seconds"] is not None else None
            ),
            petition_id=str(petition_id) if petition_id else None,
        )
