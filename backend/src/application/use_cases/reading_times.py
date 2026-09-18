"""Use cases: tempos de avaliação humana (eficiência, 1 por avaliador)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.application.ports import EvaluatorRepositoryPort
from src.application.use_cases.analysis_times import format_seconds
from src.domain.validation import REQUIRED_EVALUATIONS, ReadingTimeEntry
from src.infrastructure.persistence.analysis_time_repository_sqlite import (
    SQLiteAnalysisTimeRepository,
)
from src.infrastructure.persistence.reading_time_repository_sqlite import (
    SQLiteReadingTimeRepository,
)


class ReadingTimeConflictError(ValueError):
    """Avaliador já possui tempo registrado."""


def format_minutes(minutes: float) -> str:
    """120 -> '2h00'."""
    total = int(round(minutes))
    return f"{total // 60}h{total % 60:02d}"


PROTOTYPE_MEAN_SECONDS_FALLBACK = 1.3


def _prototype_summary(
    human_mean_minutes: float | None,
    analysis_repository: SQLiteAnalysisTimeRepository | None,
) -> dict:
    analysis_count = 0
    mean_seconds = None
    if analysis_repository is not None:
        items = analysis_repository.list_all()
        analysis_count = len(items)
        if items:
            mean_seconds = sum(item.seconds for item in items) / len(items)

    if mean_seconds is None:
        mean_seconds = PROTOTYPE_MEAN_SECONDS_FALLBACK
        source = "fallback"
    else:
        source = "measured"

    speedup = None
    if human_mean_minutes is not None and mean_seconds > 0:
        speedup = round((human_mean_minutes * 60) / mean_seconds)

    return {
        "prototype_mean_seconds": round(mean_seconds, 3),
        "prototype_mean_label": format_seconds(mean_seconds),
        "prototype_measurements": analysis_count,
        "prototype_source": source,
        "speedup_factor": speedup,
    }


class SubmitReadingTimeUseCase:
    """Registra tempo único por avaliador (máx. 30)."""

    def __init__(
        self,
        repository: SQLiteReadingTimeRepository,
        *,
        evaluators: EvaluatorRepositoryPort | None = None,
    ) -> None:
        self._repository = repository
        self._evaluators = evaluators

    def execute(
        self,
        lawyer_name: str = "",
        minutes: int = 0,
        *,
        evaluator_id: str | None = None,
        allow_update: bool = False,
    ) -> ReadingTimeEntry:
        if int(minutes) < 1:
            raise ValueError("Tempo deve ser de pelo menos 1 minuto.")

        resolved_id = (evaluator_id or "").strip() or None
        name = (lawyer_name or "").strip()

        if self._evaluators is not None:
            if not resolved_id:
                raise ValueError("Informe o avaliador (evaluator_id).")
            evaluator = self._evaluators.get(resolved_id)
            if evaluator is None:
                raise ValueError("Avaliador não encontrado.")
            name = evaluator.name
            resolved_id = evaluator.evaluator_id
        elif not name:
            raise ValueError("Informe o nome do avaliador.")

        existing = (
            self._repository.find_by_evaluator(resolved_id) if resolved_id else None
        )
        if existing is not None and not allow_update:
            raise ReadingTimeConflictError(
                "Este avaliador já possui tempo de avaliação registrado."
            )

        if existing is not None and allow_update:
            self._repository.update(
                existing.entry_id,
                name,
                int(minutes),
                evaluator_id=resolved_id,
            )
            return ReadingTimeEntry(
                entry_id=existing.entry_id,
                lawyer_name=name,
                minutes=int(minutes),
                created_at=existing.created_at,
                evaluator_id=resolved_id,
            )

        if self._repository.count() >= REQUIRED_EVALUATIONS:
            raise ReadingTimeConflictError(
                f"Limite de {REQUIRED_EVALUATIONS} tempos de avaliação atingido."
            )

        entry = ReadingTimeEntry(
            entry_id=uuid.uuid4().hex[:12],
            lawyer_name=name,
            minutes=int(minutes),
            created_at=datetime.now(timezone.utc).isoformat(),
            evaluator_id=resolved_id,
        )
        self._repository.save(entry)
        return entry


class UpdateReadingTimeUseCase:
    """Atualiza o tempo de um registro existente."""

    def __init__(
        self,
        repository: SQLiteReadingTimeRepository,
        *,
        evaluators: EvaluatorRepositoryPort | None = None,
    ) -> None:
        self._repository = repository
        self._evaluators = evaluators

    def execute(
        self,
        entry_id: str,
        lawyer_name: str = "",
        minutes: int = 0,
        *,
        evaluator_id: str | None = None,
    ) -> bool:
        if int(minutes) < 1:
            raise ValueError("Tempo deve ser de pelo menos 1 minuto.")
        current = self._repository.get(entry_id)
        if current is None:
            return False

        name = (lawyer_name or current.lawyer_name).strip()
        resolved_id = (evaluator_id or current.evaluator_id or "").strip() or None
        if self._evaluators is not None and resolved_id:
            evaluator = self._evaluators.get(resolved_id)
            if evaluator is None:
                raise ValueError("Avaliador não encontrado.")
            name = evaluator.name
            resolved_id = evaluator.evaluator_id

        return self._repository.update(
            entry_id, name, int(minutes), evaluator_id=resolved_id
        )


class DeleteReadingTimeUseCase:
    """Remove um registro de tempo."""

    def __init__(self, repository: SQLiteReadingTimeRepository) -> None:
        self._repository = repository

    def execute(self, entry_id: str) -> bool:
        return self._repository.delete(entry_id)


class ListReadingTimesUseCase:
    """Lista os até 30 tempos e agrega a média."""

    def __init__(
        self,
        repository: SQLiteReadingTimeRepository,
        analysis_repository: SQLiteAnalysisTimeRepository | None = None,
    ) -> None:
        self._repository = repository
        self._analysis_repository = analysis_repository

    def execute(self) -> tuple[list[ReadingTimeEntry], dict]:
        items = self._repository.list_all()
        if not items:
            return [], {
                "count": 0,
                "mean_minutes": None,
                "mean_label": None,
                "required": REQUIRED_EVALUATIONS,
                "remaining": REQUIRED_EVALUATIONS,
                **_prototype_summary(None, self._analysis_repository),
            }
        mean = sum(item.minutes for item in items) / len(items)
        return items, {
            "count": len(items),
            "mean_minutes": round(mean, 1),
            "mean_label": format_minutes(mean),
            "required": REQUIRED_EVALUATIONS,
            "remaining": max(0, REQUIRED_EVALUATIONS - len(items)),
            **_prototype_summary(mean, self._analysis_repository),
        }
