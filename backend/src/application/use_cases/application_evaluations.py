"""Use cases: listar snapshots de avaliação da aplicação e progresso."""

from __future__ import annotations

from src.application.ports import (
    ApplicationEvaluationRepositoryPort,
    ValidationRepositoryPort,
)
from src.domain.validation import REQUIRED_EVALUATIONS


class ListApplicationEvaluationsUseCase:
    """Lista avaliações da aplicação e progresso da campanha humana."""

    def __init__(
        self,
        repository: ApplicationEvaluationRepositoryPort,
        *,
        validations: ValidationRepositoryPort | None = None,
        linked_only: bool = True,
    ) -> None:
        self._repository = repository
        self._validations = validations
        self._linked_only = linked_only

    def execute(self) -> tuple[list[dict], dict]:
        items = (
            self._repository.list_linked()
            if self._linked_only
            else self._repository.list_all()
        )
        enriched: list[dict] = []
        for item in items:
            progress = self._progress_for(item.petition_id)
            enriched.append({"entry": item, "campaign": progress})
        means = self._repository.mean_scores()
        return enriched, {
            "count": len(enriched),
            "mean_scores": means,
            "required_evaluations": REQUIRED_EVALUATIONS,
        }

    def _progress_for(self, petition_id: str | None) -> dict:
        if not petition_id or self._validations is None:
            return {
                "required": REQUIRED_EVALUATIONS,
                "completed": 0,
                "remaining": REQUIRED_EVALUATIONS,
                "is_complete": False,
            }
        completed = self._validations.count_by_petition(petition_id)
        remaining = max(0, REQUIRED_EVALUATIONS - completed)
        return {
            "required": REQUIRED_EVALUATIONS,
            "completed": completed,
            "remaining": remaining,
            "is_complete": completed >= REQUIRED_EVALUATIONS,
        }


class DeleteAnalyzedPetitionUseCase:
    """Remove snapshot da aplicação e campanha humana da petição."""

    def __init__(
        self,
        application_evaluations: ApplicationEvaluationRepositoryPort,
        validations: ValidationRepositoryPort,
    ) -> None:
        self._application_evaluations = application_evaluations
        self._validations = validations

    def execute(self, petition_id: str) -> dict:
        petition_id = (petition_id or "").strip()
        if not petition_id:
            raise ValueError("Informe o petition_id.")
        snapshot = self._application_evaluations.get_by_petition_id(petition_id)
        if snapshot is None:
            raise LookupError("Petição analisada não encontrada.")
        deleted_validations = self._validations.delete_by_petition(petition_id)
        deleted_snapshot = self._application_evaluations.delete_by_petition_id(
            petition_id
        )
        return {
            "petition_id": petition_id,
            "petition_name": snapshot.petition_name,
            "deleted_snapshot": deleted_snapshot,
            "deleted_validations": deleted_validations,
        }


class ListEvaluatorsUseCase:
    """Lista os 30 avaliadores fixos."""

    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self):
        return self._repository.list_all()
