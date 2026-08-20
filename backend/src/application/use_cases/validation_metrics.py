"""Use case: métricas agregadas das validações humanas (dashboard do TCC)."""

from __future__ import annotations

from src.application.ports import ValidationRepositoryPort
from src.domain.validation import DIMENSION_LABELS, QUALITY_DIMENSIONS


class GetValidationMetricsUseCase:
    """Agrega médias protótipo × humano para o dashboard de métricas."""

    def __init__(self, repository: ValidationRepositoryPort) -> None:
        self._repository = repository

    def execute(self) -> dict:
        items = self._repository.list_all()

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
            "mean_final_quality": None,
            "dimensions": [],
            "problems": {**problems, "total": problems_total},
        }
        if not items:
            return base

        dimensions = []
        for name in QUALITY_DIMENSIONS:
            proto_values = [
                float(item.prototype_scores.get(name, 0.0) or 0.0) for item in items
            ]
            human_values = [
                float(item.human_scores.get(name, 0.0) or 0.0) for item in items
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
            "mean_final_quality": round(
                sum(item.final_quality for item in items) / len(items), 2
            ),
            "dimensions": dimensions,
        }
