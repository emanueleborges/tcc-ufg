"""Entidades da validação humana (lawyer-in-the-loop)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Dimensões do fluxograma Intelligent.pdf
QUALITY_DIMENSIONS: tuple[str, ...] = (
    "estrutura",
    "clareza",
    "coerencia",
    "fundamentacao",
    "consistencia",
    "elementos_essenciais",
)

DIMENSION_LABELS: dict[str, str] = {
    "estrutura": "Estrutura documental",
    "clareza": "Clareza textual",
    "coerencia": "Coerência argumentativa",
    "fundamentacao": "Fundamentação jurídica",
    "consistencia": "Consistência das informações",
    "elementos_essenciais": "Elementos essenciais",
}

ProblemVerdict = Literal["confirmed", "partial", "rejected"]


@dataclass(frozen=True)
class ProblemAssessment:
    """Julgamento humano sobre um problema apontado pelo protótipo."""

    problem: str
    verdict: ProblemVerdict
    note: str = ""


@dataclass(frozen=True)
class ComparisonMetrics:
    """Comparação quantitativa humano × protótipo."""

    mae_scores: float
    agreement_rate: float
    dimension_gaps: dict[str, float]
    problems_confirmed: int
    problems_partial: int
    problems_rejected: int
    summary: str


@dataclass(frozen=True)
class HumanValidation:
    """Registro de validação por advogado sobre uma análise do protótipo."""

    validation_id: str
    petition_id: str
    petition_name: str
    reviewer_name: str
    created_at: str
    prototype_scores: dict[str, float]
    human_scores: dict[str, float]
    problem_assessments: list[ProblemAssessment]
    # Checklist do fluxograma (validação documental)
    documentation_ok: bool
    textual_cohesion_ok: bool
    argumentative_consistency_ok: bool
    legal_basis_ok: bool
    final_quality: int  # 1–5
    comments: str
    comparison: ComparisonMetrics
    markdown_report: str = ""


@dataclass
class HumanValidationInput:
    """Dados de entrada para registrar uma validação."""

    petition_id: str
    petition_name: str
    reviewer_name: str
    prototype_scores: dict[str, float]
    human_scores: dict[str, float]
    problem_assessments: list[ProblemAssessment] = field(default_factory=list)
    documentation_ok: bool = False
    textual_cohesion_ok: bool = False
    argumentative_consistency_ok: bool = False
    legal_basis_ok: bool = False
    final_quality: int = 3
    comments: str = ""
