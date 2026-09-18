"""Use case: métricas agregadas das validações humanas (dashboard do TCC)."""

from __future__ import annotations

from src.application.ports import ValidationRepositoryPort
from src.domain.validation import (
    DIMENSION_LABELS,
    QUALITY_DIMENSIONS,
    REQUIRED_EVALUATIONS,
    HumanValidation,
)


class GetValidationMetricsUseCase:
    """Agrega médias protótipo × humano para o dashboard de métricas."""

    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(self, *, petition_id: str | None = None) -> dict:
        if petition_id:
            items = self._repository.list_by_petition(petition_id)
            progress = {
                "required_evaluations": REQUIRED_EVALUATIONS,
                "completed": len(items),
                "remaining": max(0, REQUIRED_EVALUATIONS - len(items)),
                "is_complete": len(items) >= REQUIRED_EVALUATIONS,
            }
        else:
            # Visão global oficial: somente petições com campanha 30/30
            linked = [
                item
                for item in self._repository.list_all()
                if item.evaluator_id
            ]
            by_petition: dict[str, list[HumanValidation]] = {}
            for item in linked:
                by_petition.setdefault(item.petition_id, []).append(item)
            complete_ids = {
                pid
                for pid, group in by_petition.items()
                if len(group) >= REQUIRED_EVALUATIONS
            }
            items = [
                item for item in linked if item.petition_id in complete_ids
            ]
            progress = {
                "required_evaluations": REQUIRED_EVALUATIONS,
                "completed_petitions": len(complete_ids),
                "linked_petitions": len(by_petition),
            }

        return self._aggregate(items, progress)

    def _aggregate(self, items: list[HumanValidation], progress: dict) -> dict:
        problems = {"confirmed": 0, "partial": 0, "rejected": 0}
        for item in items:
            problems["confirmed"] += item.comparison.problems_confirmed
            problems["partial"] += item.comparison.problems_partial
            problems["rejected"] += item.comparison.problems_rejected
        problems_total = sum(problems.values())

        base = {
            "count": len(items),
            "petitions": len({item.petition_id for item in items}),
            "reviewers": len({item.reviewer_name for item in items}),
            "mean_mae": None,
            "mean_agreement_rate": None,
            "mean_general_score": None,
            "mean_application_use_score": None,
            "dimensions": [],
            "problems": {**problems, "total": problems_total},
            "campaign": progress,
        }
        if not items:
            return base

        dimensions = []
        for name in (*QUALITY_DIMENSIONS, "geral"):
            proto_values = [
                float(item.prototype_scores.get(name, 0.0) or 0.0) for item in items
            ]
            human_values = [
                float(
                    item.general_score
                    if name == "geral"
                    else item.human_scores.get(name, 0.0) or 0.0
                )
                for item in items
            ]
            mean_proto = round(sum(proto_values) / len(items), 2)
            mean_human = round(sum(human_values) / len(items), 2)
            dimensions.append(
                {
                    "name": name,
                    "label": DIMENSION_LABELS.get(name, name),
                    "mean_prototype": mean_proto,
                    "mean_human": mean_human,
                    "mean_gap": round(mean_human - mean_proto, 2),
                }
            )

        return {
            **base,
            "mean_mae": round(
                sum(item.comparison.mae_scores for item in items) / len(items), 2
            ),
            "mean_agreement_rate": round(
                sum(item.comparison.agreement_rate for item in items) / len(items), 3
            ),
            "mean_general_score": round(
                sum(item.general_score for item in items) / len(items), 2
            ),
            "mean_application_use_score": round(
                sum(item.application_use_score for item in items) / len(items), 2
            ),
            "dimensions": dimensions,
        }
