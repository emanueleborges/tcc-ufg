"""Ports (interfaces) da camada de aplicação.

Definem os contratos que os adapters de infraestrutura devem implementar.
Use cases dependem somente destas abstrações, nunca de implementações
concretas, mantendo a inversão de dependência (DIP).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

import numpy as np

from src.domain.chat import ChatAnswer, ChatMessage, Intent
from src.domain.entities import (
    Chunk,
    DocumentSummary,
    ReviewResult,
    WebReference,
)


@runtime_checkable
class PdfReaderPort(Protocol):
    """Lê páginas e texto de arquivos PDF (com fallback de OCR)."""

    def read_pages(self, path: Path) -> list[str]: ...

    def read_text(self, path: Path) -> str: ...


@runtime_checkable
class PdfWriterPort(Protocol):
    """Converte markdown em PDF impresso."""

    def markdown_to_pdf(self, markdown: str, output_path: Path) -> Path: ...


@runtime_checkable
class EmbeddingEnginePort(Protocol):
    """Gera vetores normalizados a partir de textos."""

    def encode_passages(self, texts: Iterable[str]) -> np.ndarray: ...

    def encode_query(self, text: str) -> np.ndarray: ...


@runtime_checkable
class IndexRepositoryPort(Protocol):
    """Persistência da base RAG (chunks + documentos + embeddings)."""

    def exists(self) -> bool: ...

    def save(
        self,
        chunks: list[Chunk],
        documents: list[DocumentSummary],
        embeddings: np.ndarray,
    ) -> None: ...

    def load(self) -> tuple[list[Chunk], list[DocumentSummary], np.ndarray]: ...


@runtime_checkable
class WebSearchPort(Protocol):
    """Cliente de busca na web por referências jurídicas externas."""

    def search_references(
        self,
        review: ReviewResult,
        max_results: int,
    ) -> list[WebReference]: ...

    def search_text(
        self,
        query: str,
        max_results: int,
    ) -> list[WebReference]: ...


@runtime_checkable
class ConversationalLLMPort(Protocol):
    """LLM conversacional (LangChain-backed) usado pelo chatbot."""

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> str: ...


@runtime_checkable
class ChatAnswerPort(Protocol):
    """Estratégia de geração de resposta para uma intenção do chat.

    Cada implementação representa uma fonte (RAG, Ollama, Internet, etc.)
    e sabe responder a uma mensagem produzindo um ``ChatAnswer`` com a
    devida marcação de origem e citações.
    """

    intent: Intent

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer: ...
