"""Use case: registrar e consultar validações humanas por petição."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.application.ports import (
    ApplicationEvaluationRepositoryPort,
    EvaluatorRepositoryPort,
    ValidationRepositoryPort,
)
from src.domain.validation import (
    QUALITY_DIMENSIONS,
    REQUIRED_EVALUATIONS,
    CampaignProgress,
    HumanValidation,
    HumanValidationInput,
)
from src.services.human_comparison import build_validation
from src.services.scoring import quality_scores_only


class CohortConflictError(ValueError):
    """Conflito de coorte (duplicata ou campanha completa)."""


class SubmitHumanValidationUseCase:
    """Persiste a validação do avaliador e calcula a comparação com o protótipo."""

    def __init__(
        self,
        repository: ValidationRepositoryPort,
        *,
        evaluators: EvaluatorRepositoryPort | None = None,
        application_evaluations: ApplicationEvaluationRepositoryPort | None = None,
    ) -> None:
        self._repository = repository
        self._evaluators = evaluators
        self._application_evaluations = application_evaluations

    def execute(self, payload: HumanValidationInput) -> HumanValidation:
        resolved = self._resolve_cohort(payload, exclude_validation_id=None)
        normalized = self._normalize(resolved)
        validation_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        validation = build_validation(validation_id, created_at, normalized)
        self._repository.save(validation)
        return validation

    def update(
        self, validation_id: str, payload: HumanValidationInput
    ) -> HumanValidation:
        current = self._repository.get(validation_id)
        if current is None:
            raise ValueError("Validação não encontrada.")
        resolved = self._resolve_cohort(payload, exclude_validation_id=validation_id)
        normalized = self._normalize(resolved)
        validation = build_validation(validation_id, current.created_at, normalized)
        self._repository.save(validation)
        return validation

    def _resolve_cohort(
        self,
        payload: HumanValidationInput,
        *,
        exclude_validation_id: str | None,
    ) -> HumanValidationInput:
        petition_id = (payload.petition_id or "").strip()
        if not petition_id:
            raise ValueError("Informe o petition_id da análise.")

        evaluator_id = (payload.evaluator_id or "").strip() or None
        reviewer_name = (payload.reviewer_name or "").strip()

        if self._evaluators is not None:
            if not evaluator_id:
                raise ValueError("Informe o avaliador (evaluator_id).")
            evaluator = self._evaluators.get(evaluator_id)
            if evaluator is None:
                raise ValueError("Avaliador não encontrado.")
            reviewer_name = evaluator.name
        elif not reviewer_name:
            raise ValueError("Informe o nome do avaliador.")

        petition_name = (payload.petition_name or "").strip()
        prototype_scores = dict(payload.prototype_scores or {})

        if self._application_evaluations is not None:
            snapshot = self._application_evaluations.get_by_petition_id(petition_id)
            if snapshot is None:
                raise ValueError(
                    "Petição não encontrada ou ainda sem análise da aplicação."
                )
            petition_name = snapshot.petition_name or petition_name
            if not prototype_scores:
                prototype_scores = dict(snapshot.scores)

        if evaluator_id:
            existing = self._repository.find_by_petition_evaluator(
                petition_id, evaluator_id
            )
            if existing is not None and existing.validation_id != exclude_validation_id:
                raise CohortConflictError(
                    "Este avaliador já respondeu esta petição."
                )
            if exclude_validation_id is None:
                completed = self._repository.count_by_petition(petition_id)
                if completed >= REQUIRED_EVALUATIONS:
                    raise CohortConflictError(
                        f"Campanha completa ({REQUIRED_EVALUATIONS}/{REQUIRED_EVALUATIONS})."
                    )

        return HumanValidationInput(
            petition_id=petition_id,
            petition_name=petition_name,
            reviewer_name=reviewer_name,
            prototype_scores=prototype_scores,
            human_scores=dict(payload.human_scores or {}),
            problem_assessments=list(payload.problem_assessments),
            documentation_ok=payload.documentation_ok,
            textual_cohesion_ok=payload.textual_cohesion_ok,
            argumentative_consistency_ok=payload.argumentative_consistency_ok,
            legal_basis_ok=payload.legal_basis_ok,
            general_score=payload.general_score,
            application_use_score=payload.application_use_score,
            comments=payload.comments,
            reading_minutes=payload.reading_minutes,
            evaluator_id=evaluator_id,
        )

    def _normalize(self, payload: HumanValidationInput) -> HumanValidationInput:
        if not payload.reviewer_name.strip():
            raise ValueError("Informe o nome do avaliador.")
        if not payload.petition_id.strip():
            raise ValueError("Informe o petition_id da análise.")

        human_scores = quality_scores_only(payload.human_scores)
        for name in QUALITY_DIMENSIONS:
            value = float(human_scores.get(name, 0.0) or 0.0)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"Confiança inválida para '{name}' (0–100%).")
            human_scores[name] = value

        for label, value in (
            ("geral", payload.general_score),
            ("uso da aplicação", payload.application_use_score),
        ):
            if not 0.0 <= float(value) <= 100.0:
                raise ValueError(f"Confiança inválida para '{label}' (0–100%).")

        use_score = float(payload.application_use_score)
        if use_score not in (0.0, 100.0):
            use_score = 100.0 if use_score >= 50.0 else 0.0

        if int(payload.reading_minutes) < 0:
            raise ValueError("Tempo inválido.")

        prototype_raw = dict(payload.prototype_scores or {})
        sample_values = [float(v or 0.0) for v in prototype_raw.values()]
        scale_to_percent = bool(sample_values) and max(sample_values) <= 10.0

        prototype_scores = quality_scores_only(prototype_raw)
        if "geral" in prototype_raw:
            prototype_scores["geral"] = float(prototype_raw["geral"])
        if scale_to_percent:
            prototype_scores = {
                name: round(float(value) * 10.0, 2)
                for name, value in prototype_scores.items()
            }

        return HumanValidationInput(
            petition_id=payload.petition_id.strip(),
            petition_name=payload.petition_name.strip(),
            reviewer_name=payload.reviewer_name.strip(),
            prototype_scores=prototype_scores,
            human_scores=human_scores,
            problem_assessments=list(payload.problem_assessments),
            documentation_ok=payload.documentation_ok,
            textual_cohesion_ok=payload.textual_cohesion_ok,
            argumentative_consistency_ok=payload.argumentative_consistency_ok,
            legal_basis_ok=payload.legal_basis_ok,
            general_score=float(payload.general_score),
            application_use_score=use_score,
            comments=payload.comments.strip(),
            reading_minutes=int(payload.reading_minutes),
            evaluator_id=payload.evaluator_id,
        )


class ListHumanValidationsUseCase:
    """Lista validações e agrega métricas de aderência."""

    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(
        self, *, petition_id: str | None = None
    ) -> tuple[list[HumanValidation], dict]:
        if petition_id:
            items = self._repository.list_by_petition(petition_id)
        else:
            items = self._repository.list_all()
        if not items:
            return [], {
                "count": 0,
                "mean_mae": None,
                "mean_agreement_rate": None,
                "mean_general_score": None,
                "mean_application_use_score": None,
            }

        mean_mae = round(
            sum(item.comparison.mae_scores for item in items) / len(items), 2
        )
        mean_agreement = round(
            sum(item.comparison.agreement_rate for item in items) / len(items), 3
        )
        mean_general = round(
            sum(item.general_score for item in items) / len(items), 2
        )
        mean_application_use = round(
            sum(item.application_use_score for item in items) / len(items), 2
        )
        return items, {
            "count": len(items),
            "mean_mae": mean_mae,
            "mean_agreement_rate": mean_agreement,
            "mean_general_score": mean_general,
            "mean_application_use_score": mean_application_use,
        }


class GetHumanValidationUseCase:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(self, validation_id: str) -> HumanValidation | None:
        return self._repository.get(validation_id)


class DeleteHumanValidationUseCase:
    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(self, validation_id: str) -> bool:
        return self._repository.delete(validation_id)


class GetCampaignProgressUseCase:
    """Progresso N/30 da campanha humana de uma petição."""

    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(self, petition_id: str) -> CampaignProgress:
        completed = self._repository.count_by_petition(petition_id)
        remaining = max(0, REQUIRED_EVALUATIONS - completed)
        return CampaignProgress(
            petition_id=petition_id,
            required=REQUIRED_EVALUATIONS,
            completed=completed,
            remaining=remaining,
            is_complete=completed >= REQUIRED_EVALUATIONS,
        )
