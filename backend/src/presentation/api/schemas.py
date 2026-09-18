"""Contratos Pydantic da API — formato próximo ao Chat Completions da OpenAI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    """Mensagem enviada pelo cliente (histórico + mensagem atual)."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatCompletionRequest(BaseModel):
    """
    Request estilo OpenAI Chat Completions.

    O backend roteia automaticamente entre RAG, Ollama e Internet.
    """

    model: str = Field(
        default="qwen2.5-coder:7b",
        description="Modelo Ollama usado nas respostas que passam pelo LLM.",
    )
    messages: list[ChatMessageIn] = Field(
        ...,
        min_length=1,
        description="Histórico da conversa; a última mensagem do usuário é a pergunta atual.",
    )
    petition_id: Optional[str] = Field(
        default=None,
        description="ID retornado por POST /v1/uploads (ativa análise da petição).",
    )
    rag_top_k: int = Field(default=8, ge=1, le=20)
    web_max_results: int = Field(default=5, ge=1, le=15)
    persona_id: str = Field(
        default="geral",
        description="Persona jurídica (especialista) aplicada ao system prompt.",
    )


class CitationOut(BaseModel):
    title: str
    detail: str = ""
    url: str = ""


class RoutingOut(BaseModel):
    intent: str
    mode: str
    reason: str


class SourceOut(BaseModel):
    id: str
    label: str
    icon: str


class ChatMessageOut(BaseModel):
    role: Literal["assistant"]
    content: str


class ChatChoiceOut(BaseModel):
    index: int = 0
    message: ChatMessageOut
    finish_reason: Literal["stop"] = "stop"


class PromptInjectionFindingOut(BaseModel):
    pattern_id: str
    severity: str
    description: str
    excerpt: str
    matched: str = ""
    owasp_categories: list[str] = Field(default_factory=list)


class PromptInjectionOut(BaseModel):
    """Resultado da varredura — alinhado ao OWASP LLM Top 10 2025 (LLM01)."""

    risk: Literal["none", "low", "medium", "high", "critical"] = "none"
    score: int = 0
    summary: str = ""
    findings: list[PromptInjectionFindingOut] = Field(default_factory=list)
    scanned_chars: int = 0
    owasp_id: str = "LLM01:2025"
    owasp_name: str = "Prompt Injection"
    owasp_url: str = "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"
    attack_types: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    verdict: Literal["clean", "suspicious", "malicious"] = "clean"


class AnalysisOut(BaseModel):
    """Painel estruturado da análise crítica (modo clássico no chat)."""

    scores: dict[str, float] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""
    prompt_injection: Optional[PromptInjectionOut] = None


class ChatCompletionResponse(BaseModel):
    """Response estilo OpenAI Chat Completions + metadados do crítico jurídico."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoiceOut]
    source: SourceOut
    routing: RoutingOut
    persona: Optional[PersonaOut] = None
    citations: list[CitationOut] = Field(default_factory=list)
    analysis: Optional[AnalysisOut] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(BaseModel):
    petition_id: str
    file_name: str
    path: str
    size_bytes: int
    uploaded_at: datetime


class IndexStatusResponse(BaseModel):
    exists: bool
    index_dir: str
    documents: Optional[int] = None
    chunks: Optional[int] = None


class IndexRebuildResponse(BaseModel):
    documents: int
    chunks: int
    report_path: str
    index_dir: str


class ScrapeResponse(BaseModel):
    total_documents: int
    message: str
    new_accepted: int = 0
    new_rejected: int = 0
    new_partial: int = 0
    candidates_found: int = 0


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "critico-juridico-api"
    version: str = "1.0.0"


class ModelOut(BaseModel):
    id: str
    object: Literal["model"] = "model"
    owned_by: str
    description: str


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelOut]


class PersonaOut(BaseModel):
    id: str
    label: str
    description: str


class PersonasListResponse(BaseModel):
    default_id: str
    data: list[PersonaOut]


class ProblemAssessmentIn(BaseModel):
    problem: str
    verdict: Literal["confirmed", "partial", "rejected"]
    note: str = ""


class HumanValidationCreateRequest(BaseModel):
    """Validação lawyer-in-the-loop sobre uma análise do protótipo."""

    petition_id: str = Field(..., min_length=1)
    petition_name: str = ""
    evaluator_id: str = Field(..., min_length=1)
    reviewer_name: str = ""
    prototype_scores: dict[str, float] = Field(default_factory=dict)
    human_scores: dict[str, float] = Field(default_factory=dict)
    problem_assessments: list[ProblemAssessmentIn] = Field(default_factory=list)
    documentation_ok: bool = False
    textual_cohesion_ok: bool = False
    argumentative_consistency_ok: bool = False
    legal_basis_ok: bool = False
    general_score: float = Field(default=0.0, ge=0.0, le=100.0)
    application_use_score: float = Field(default=0.0, ge=0.0, le=100.0)
    comments: str = ""
    reading_minutes: int = Field(
        default=0,
        ge=0,
        description="Legado opcional; tempo oficial fica em /v1/reading-times (1 por avaliador).",
    )


class ComparisonOut(BaseModel):
    mae_scores: float
    agreement_rate: float
    dimension_gaps: dict[str, float]
    problems_confirmed: int
    problems_partial: int
    problems_rejected: int
    summary: str
    general_gap: float = 0.0


class ProblemAssessmentOut(BaseModel):
    problem: str
    verdict: Literal["confirmed", "partial", "rejected"]
    note: str = ""


class HumanValidationOut(BaseModel):
    validation_id: str
    petition_id: str
    petition_name: str
    reviewer_name: str
    evaluator_id: Optional[str] = None
    created_at: str
    prototype_scores: dict[str, float]
    human_scores: dict[str, float]
    problem_assessments: list[ProblemAssessmentOut]
    documentation_ok: bool
    textual_cohesion_ok: bool
    argumentative_consistency_ok: bool
    legal_basis_ok: bool
    general_score: float
    application_use_score: float
    comments: str
    reading_minutes: int = 0
    comparison: ComparisonOut
    markdown_report: str = ""


class ValidationSummaryOut(BaseModel):
    count: int
    mean_mae: Optional[float] = None
    mean_agreement_rate: Optional[float] = None
    mean_general_score: Optional[float] = None
    mean_application_use_score: Optional[float] = None


class DimensionMetricOut(BaseModel):
    """Média por dimensão: protótipo × humano × gap médio."""

    name: str
    label: str
    mean_prototype: float
    mean_human: float
    mean_gap: float


class ProblemVerdictsOut(BaseModel):
    confirmed: int = 0
    partial: int = 0
    rejected: int = 0
    total: int = 0


class CampaignProgressOut(BaseModel):
    required_evaluations: int = 30
    completed: int = 0
    remaining: int = 30
    is_complete: bool = False
    completed_petitions: Optional[int] = None
    linked_petitions: Optional[int] = None


class ValidationMetricsResponse(BaseModel):
    """Agregados do dashboard de validação humana (TCC)."""

    count: int
    petitions: int
    reviewers: int
    mean_mae: Optional[float] = None
    mean_agreement_rate: Optional[float] = None
    mean_general_score: Optional[float] = None
    mean_application_use_score: Optional[float] = None
    dimensions: list[DimensionMetricOut] = Field(default_factory=list)
    problems: ProblemVerdictsOut = Field(default_factory=ProblemVerdictsOut)
    campaign: Optional[dict[str, Any]] = None


class EvaluatorOut(BaseModel):
    evaluator_id: str
    name: str
    sort_order: int
    has_responded: bool = False
    validation_id: Optional[str] = None


class EvaluatorsListResponse(BaseModel):
    items: list[EvaluatorOut]
    required_evaluations: int = 30


class PetitionCampaignOut(BaseModel):
    petition_id: str
    required: int
    completed: int
    remaining: int
    is_complete: bool


# --- Tempos de leitura humana (advogado + tempo gasto) ---


class ReadingTimeCreateRequest(BaseModel):
    evaluator_id: str = Field(..., min_length=1)
    lawyer_name: str = ""
    minutes: int = Field(..., ge=1)


class ReadingTimeUpdateRequest(BaseModel):
    evaluator_id: str = ""
    lawyer_name: str = ""
    minutes: int = Field(..., ge=1)


class ReadingTimeOut(BaseModel):
    entry_id: str
    lawyer_name: str
    minutes: int
    label: str
    created_at: str
    evaluator_id: Optional[str] = None


class ReadingTimeSummaryOut(BaseModel):
    count: int
    mean_minutes: Optional[float] = None
    mean_label: Optional[str] = None
    required: int = 30
    remaining: Optional[int] = None
    prototype_mean_seconds: float = 1.3
    prototype_mean_label: str = "1,3 s"
    prototype_measurements: int = 0
    prototype_source: str = "fallback"
    speedup_factor: Optional[int] = None


class AnalysisTimeOut(BaseModel):
    entry_id: str
    petition_name: str
    seconds: float
    label: str
    created_at: str
    source: str


class AnalysisTimeSummaryOut(BaseModel):
    count: int
    mean_seconds: Optional[float] = None
    mean_label: Optional[str] = None


class AnalysisTimeListResponse(BaseModel):
    items: list[AnalysisTimeOut]
    summary: AnalysisTimeSummaryOut


class ApplicationEvaluationOut(BaseModel):
    entry_id: str
    petition_id: Optional[str] = None
    petition_name: str
    scores: dict[str, float]
    problems: list[str]
    injection_risk: str
    injection_score: int
    created_at: str
    seconds: Optional[float] = None
    campaign: Optional[PetitionCampaignOut] = None


class ApplicationEvaluationSummaryOut(BaseModel):
    count: int
    mean_scores: Optional[dict[str, float]] = None
    required_evaluations: int = 30


class ApplicationEvaluationListResponse(BaseModel):
    items: list[ApplicationEvaluationOut]
    summary: ApplicationEvaluationSummaryOut


class DeleteAnalyzedPetitionResponse(BaseModel):
    petition_id: str
    petition_name: str
    deleted_snapshot: bool
    deleted_validations: int


class MeasureAnalysisTimeRequest(BaseModel):
    runs: int = 3
    petition_id: Optional[str] = None


class MeasureAnalysisTimeResponse(BaseModel):
    petition_name: str
    runs: int
    mean_seconds: float
    mean_label: str
    items: list[AnalysisTimeOut]


class ReadingTimeListResponse(BaseModel):
    items: list[ReadingTimeOut]
    summary: ReadingTimeSummaryOut


class HumanValidationListResponse(BaseModel):
    items: list[HumanValidationOut]
    summary: ValidationSummaryOut


class ErrorResponse(BaseModel):
    detail: str
