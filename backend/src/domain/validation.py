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

REQUIRED_EVALUATIONS = 30

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
    general_gap: float = 0.0


@dataclass(frozen=True)
class Evaluator:
    """Avaliador fixo da coorte de 30."""

    evaluator_id: str
    name: str
    sort_order: int


@dataclass(frozen=True)
class CampaignProgress:
    """Progresso da campanha humana de uma petição."""

    petition_id: str
    required: int
    completed: int
    remaining: int
    is_complete: bool


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
    general_score: float  # 0–100 (confiança %)
    application_use_score: float  # 0 = NÃO, 100 = SIM
    comments: str
    comparison: ComparisonMetrics
    markdown_report: str = ""
    reading_minutes: int = 0  # tempo de avaliação humana
    evaluator_id: str | None = None  # None = legado sem vínculo


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
    general_score: float = 0.0
    application_use_score: float = 0.0  # 0 = NÃO, 100 = SIM
    comments: str = ""
    reading_minutes: int = 0
    evaluator_id: str | None = None


@dataclass(frozen=True)
class ReadingTimeEntry:
    """Registro único de tempo de avaliação humana por avaliador (eficiência)."""

    entry_id: str
    lawyer_name: str
    minutes: int
    created_at: str
    evaluator_id: str | None = None


@dataclass(frozen=True)
class AnalysisTimeEntry:
    """Tempo real gasto pela aplicação ao analisar uma petição."""

    entry_id: str
    petition_name: str
    seconds: float
    created_at: str
    source: str = "auto"  # auto | measure


@dataclass(frozen=True)
class ApplicationEvaluationEntry:
    """Snapshot das notas da aplicação em uma análise de petição (0–100%)."""

    entry_id: str
    petition_name: str
    scores: dict[str, float]
    problems: list[str]
    injection_risk: str
    injection_score: int
    created_at: str
    seconds: float | None = None
    petition_id: str | None = None  # None = legado não vinculado
