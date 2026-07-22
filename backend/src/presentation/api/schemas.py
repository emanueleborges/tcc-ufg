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
        default="llama3:latest",
        description="Modelo Ollama usado nas respostas que passam pelo LLM.",
    )
    messages: list[ChatMessageIn] = Field(
        ...,
        min_length=1,
        description="Histórico da conversa; a última mensagem do usuário é a pergunta atual.",
    )
    petition_id: Optional[str] = Field(
        default=None,
        description="ID retornado por POST /v1/uploads (ativa análise/recriação).",
    )
    rag_top_k: int = Field(default=8, ge=1, le=20)
    web_max_results: int = Field(default=5, ge=1, le=15)
    use_internet_on_recreate: bool = Field(
        default=True,
        description="Usar DuckDuckGo ao recriar petição.",
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


class AnalysisOut(BaseModel):
    """Painel estruturado da análise crítica (modo clássico no chat)."""

    scores: dict[str, float] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    markdown: str = ""


class RecreationOut(BaseModel):
    """Resultado da recriação de petição."""

    markdown: str
    warnings: list[str] = Field(default_factory=list)
    used_ollama: bool = False


class ChatCompletionResponse(BaseModel):
    """Response estilo OpenAI Chat Completions + metadados do crítico jurídico."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoiceOut]
    source: SourceOut
    routing: RoutingOut
    citations: list[CitationOut] = Field(default_factory=list)
    analysis: Optional[AnalysisOut] = None
    recreation: Optional[RecreationOut] = None
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


class ErrorResponse(BaseModel):
    detail: str
