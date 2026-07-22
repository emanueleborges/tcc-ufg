"""Entidades de domínio do chatbot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AnswerSource(str, Enum):
    """Origem de cada resposta exibida no chat."""

    RAG = "rag"
    OLLAMA = "ollama"
    INTERNET = "internet"
    PETITION_ANALYSIS = "petition_analysis"
    PETITION_RECREATION = "petition_recreation"
    SYSTEM = "system"

    @property
    def label(self) -> str:
        return {
            AnswerSource.RAG: "Base RAG jurídica",
            AnswerSource.OLLAMA: "Ollama local",
            AnswerSource.INTERNET: "Internet (DuckDuckGo)",
            AnswerSource.PETITION_ANALYSIS: "Análise crítica da petição",
            AnswerSource.PETITION_RECREATION: "Recriação da petição",
            AnswerSource.SYSTEM: "Sistema",
        }[self]

    @property
    def icon(self) -> str:
        return {
            AnswerSource.RAG: "📚",
            AnswerSource.OLLAMA: "🤖",
            AnswerSource.INTERNET: "🌐",
            AnswerSource.PETITION_ANALYSIS: "⚖️",
            AnswerSource.PETITION_RECREATION: "✍️",
            AnswerSource.SYSTEM: "ℹ️",
        }[self]


class Intent(str, Enum):
    """Intenção detectada na mensagem do usuário."""

    ANALYZE_PETITION = "analyze_petition"
    RECREATE_PETITION = "recreate_petition"
    ASK_RAG = "ask_rag"
    ASK_INTERNET = "ask_internet"
    ASK_OLLAMA = "ask_ollama"


class ChatRole(str, Enum):
    """Papel de quem enviou a mensagem."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Citation:
    """Citação que fundamenta uma resposta do assistente."""

    title: str
    detail: str = ""
    url: str = ""


@dataclass(frozen=True)
class ChatAnswer:
    """Resposta gerada pelo assistente, com a fonte e citações."""

    text: str
    source: AnswerSource
    intent: Intent
    citations: list[Citation] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class ChatMessage:
    """Mensagem trocada no chat (mutável apenas no histórico)."""

    role: ChatRole
    content: str
    source: Optional[AnswerSource] = None
    citations: list[Citation] = field(default_factory=list)
    routing_mode: Optional[str] = None
    routing_reason: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
