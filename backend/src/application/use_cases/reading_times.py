"""Use cases: registrar e listar tempos de leitura humana de petições."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.application.use_cases.analysis_times import format_seconds
from src.domain.validation import ReadingTimeEntry
from src.infrastructure.persistence.analysis_time_repository_sqlite import (
    SQLiteAnalysisTimeRepository,
)
from src.infrastructure.persistence.reading_time_repository_sqlite import (
    SQLiteReadingTimeRepository,
)


def format_minutes(minutes: float) -> str:
    """120 -> '2h00'."""
    total = int(round(minutes))
    return f"{total // 60}h{total % 60:02d}"


# Fallback só quando ainda não há medições reais da aplicação.
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
    """Registra o tempo que um advogado gastou lendo uma petição."""

    def __init__(self, repository: SQLiteReadingTimeRepository) -> None:
        self._repository = repository

    def execute(self, lawyer_name: str, minutes: int) -> ReadingTimeEntry:
        if not lawyer_name.strip():
            raise ValueError("Informe o nome do advogado.")
        if int(minutes) < 1:
            raise ValueError("Tempo deve ser de pelo menos 1 minuto.")
        entry = ReadingTimeEntry(
            entry_id=uuid.uuid4().hex[:12],
            lawyer_name=lawyer_name.strip(),
            minutes=int(minutes),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._repository.save(entry)
        return entry


class UpdateReadingTimeUseCase:
    """Atualiza nome/tempo de um registro existente."""

    def __init__(self, repository: SQLiteReadingTimeRepository) -> None:
        self._repository = repository

    def execute(self, entry_id: str, lawyer_name: str, minutes: int) -> bool:
        if not lawyer_name.strip():
            raise ValueError("Informe o nome do advogado.")
        if int(minutes) < 1:
            raise ValueError("Tempo deve ser de pelo menos 1 minuto.")
        return self._repository.update(entry_id, lawyer_name.strip(), int(minutes))


class DeleteReadingTimeUseCase:
    """Remove um registro de tempo de leitura."""

    def __init__(self, repository: SQLiteReadingTimeRepository) -> None:
        self._repository = repository

    def execute(self, entry_id: str) -> bool:
        return self._repository.delete(entry_id)


class ListReadingTimesUseCase:
    """Lista os registros e agrega o tempo médio de leitura."""

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
                **_prototype_summary(None, self._analysis_repository),
            }
        mean = sum(item.minutes for item in items) / len(items)
        return items, {
            "count": len(items),
            "mean_minutes": round(mean, 1),
            "mean_label": format_minutes(mean),
            **_prototype_summary(mean, self._analysis_repository),
        }
