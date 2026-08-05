"""Persistência em disco das validações humanas."""

from __future__ import annotations

import json
from pathlib import Path

from src.domain.validation import (
    ComparisonMetrics,
    HumanValidation,
    ProblemAssessment,
)


class FileSystemValidationRepository:
    """Salva/carrega validações como JSON em ``validacoes/``."""

    def __init__(self, validations_dir: Path) -> None:
        self._dir = validations_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, validation: HumanValidation) -> Path:
        path = self._dir / f"{validation.validation_id}.json"
        path.write_text(
            json.dumps(_to_dict(validation), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report = self._dir / f"{validation.validation_id}.md"
        report.write_text(validation.markdown_report, encoding="utf-8")
        return path

    def get(self, validation_id: str) -> HumanValidation | None:
        path = self._dir / f"{validation_id}.json"
        if not path.exists():
            return None
        return _from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_all(self) -> list[HumanValidation]:
        items: list[HumanValidation] = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                items.append(_from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return items


def _to_dict(validation: HumanValidation) -> dict:
    return {
        "validation_id": validation.validation_id,
        "petition_id": validation.petition_id,
        "petition_name": validation.petition_name,
        "reviewer_name": validation.reviewer_name,
        "created_at": validation.created_at,
        "prototype_scores": validation.prototype_scores,
        "human_scores": validation.human_scores,
        "problem_assessments": [
            {
                "problem": item.problem,
                "verdict": item.verdict,
                "note": item.note,
            }
            for item in validation.problem_assessments
        ],
        "documentation_ok": validation.documentation_ok,
        "textual_cohesion_ok": validation.textual_cohesion_ok,
        "argumentative_consistency_ok": validation.argumentative_consistency_ok,
        "legal_basis_ok": validation.legal_basis_ok,
        "final_quality": validation.final_quality,
        "comments": validation.comments,
        "comparison": {
            "mae_scores": validation.comparison.mae_scores,
            "agreement_rate": validation.comparison.agreement_rate,
            "dimension_gaps": validation.comparison.dimension_gaps,
            "problems_confirmed": validation.comparison.problems_confirmed,
            "problems_partial": validation.comparison.problems_partial,
            "problems_rejected": validation.comparison.problems_rejected,
            "summary": validation.comparison.summary,
        },
        "markdown_report": validation.markdown_report,
    }


def _from_dict(data: dict) -> HumanValidation:
    cmp_data = data["comparison"]
    return HumanValidation(
        validation_id=data["validation_id"],
        petition_id=data["petition_id"],
        petition_name=data.get("petition_name", ""),
        reviewer_name=data["reviewer_name"],
        created_at=data["created_at"],
        prototype_scores=dict(data.get("prototype_scores") or {}),
        human_scores=dict(data.get("human_scores") or {}),
        problem_assessments=[
            ProblemAssessment(
                problem=item["problem"],
                verdict=item["verdict"],
                note=item.get("note", ""),
            )
            for item in data.get("problem_assessments") or []
        ],
        documentation_ok=bool(data.get("documentation_ok")),
        textual_cohesion_ok=bool(data.get("textual_cohesion_ok")),
        argumentative_consistency_ok=bool(data.get("argumentative_consistency_ok")),
        legal_basis_ok=bool(data.get("legal_basis_ok")),
        final_quality=int(data.get("final_quality", 3)),
        comments=str(data.get("comments") or ""),
        comparison=ComparisonMetrics(
            mae_scores=float(cmp_data["mae_scores"]),
            agreement_rate=float(cmp_data["agreement_rate"]),
            dimension_gaps=dict(cmp_data.get("dimension_gaps") or {}),
            problems_confirmed=int(cmp_data.get("problems_confirmed", 0)),
            problems_partial=int(cmp_data.get("problems_partial", 0)),
            problems_rejected=int(cmp_data.get("problems_rejected", 0)),
            summary=str(cmp_data.get("summary") or ""),
        ),
        markdown_report=str(data.get("markdown_report") or ""),
    )
