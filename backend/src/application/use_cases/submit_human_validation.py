"""Use case: registrar e consultar validações humanas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.domain.validation import (
    QUALITY_DIMENSIONS,
    HumanValidation,
    HumanValidationInput,
)
from src.infrastructure.persistence.validation_repository import (
    FileSystemValidationRepository,
)
from src.services.human_comparison import build_validation
from src.services.scoring import quality_scores_only


class SubmitHumanValidationUseCase:
    """Persiste a validação do advogado e calcula a comparação com o protótipo."""

    def __init__(self, repository: FileSystemValidationRepository) -> None:
        self._repository = repository

    def execute(self, payload: HumanValidationInput) -> HumanValidation:
        if not payload.reviewer_name.strip():
            raise ValueError("Informe o nome do avaliador.")
        if not payload.petition_id.strip():
            raise ValueError("Informe o petition_id da análise.")

        human_scores = quality_scores_only(payload.human_scores)
        for name in QUALITY_DIMENSIONS:
            value = float(human_scores.get(name, 0.0) or 0.0)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"Score humano inválido para '{name}' (0–10).")
            human_scores[name] = value

        if not 1 <= int(payload.final_quality) <= 5:
            raise ValueError("Qualidade final deve estar entre 1 e 5.")

        normalized = HumanValidationInput(
            petition_id=payload.petition_id.strip(),
            petition_name=payload.petition_name.strip(),
            reviewer_name=payload.reviewer_name.strip(),
            prototype_scores=quality_scores_only(payload.prototype_scores),
            human_scores=human_scores,
            problem_assessments=list(payload.problem_assessments),
            documentation_ok=payload.documentation_ok,
            textual_cohesion_ok=payload.textual_cohesion_ok,
            argumentative_consistency_ok=payload.argumentative_consistency_ok,
            legal_basis_ok=payload.legal_basis_ok,
            final_quality=int(payload.final_quality),
            comments=payload.comments.strip(),
        )

        validation_id = uuid.uuid4().hex[:12]
        created_at = datetime.now(timezone.utc).isoformat()
        validation = build_validation(validation_id, created_at, normalized)
        self._repository.save(validation)
        return validation


class ListHumanValidationsUseCase:
    """Lista validações e agrega métricas de aderência."""

    def __init__(self, repository: FileSystemValidationRepository) -> None:
        self._repository = repository

    def execute(self) -> tuple[list[HumanValidation], dict]:
        items = self._repository.list_all()
        if not items:
            return [], {
                "count": 0,
                "mean_mae": None,
                "mean_agreement_rate": None,
                "mean_final_quality": None,
            }

        mean_mae = round(
            sum(item.comparison.mae_scores for item in items) / len(items), 2
        )
        mean_agreement = round(
            sum(item.comparison.agreement_rate for item in items) / len(items), 3
        )
        mean_quality = round(
            sum(item.final_quality for item in items) / len(items), 2
        )
        return items, {
            "count": len(items),
            "mean_mae": mean_mae,
            "mean_agreement_rate": mean_agreement,
            "mean_final_quality": mean_quality,
        }


class GetHumanValidationUseCase:
    def __init__(self, repository: FileSystemValidationRepository) -> None:
        self._repository = repository

    def execute(self, validation_id: str) -> HumanValidation | None:
        return self._repository.get(validation_id)
