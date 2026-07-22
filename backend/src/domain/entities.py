"""Entidades de domínio do crítico jurídico.

Estruturas de dados puras (dataclasses) sem dependências externas.
São o coração do sistema e podem ser usadas por qualquer camada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

FeatureValue = Union[int, bool, float]
FeatureMap = dict[str, FeatureValue]


@dataclass(frozen=True)
class Chunk:
    """Trecho coeso de uma petição, com sua seção e features extraídas."""

    chunk_id: str
    document_id: str
    file_name: str
    section: str
    text: str
    page_start: int
    page_end: int
    features: FeatureMap


@dataclass(frozen=True)
class DocumentSummary:
    """Resumo agregado de um documento indexado na base RAG."""

    document_id: str
    file_name: str
    path: str
    chars: int
    chunks: int
    sections: dict[str, int]
    features: FeatureMap


@dataclass(frozen=True)
class SimilarChunk:
    """Resultado de busca semântica: chunk + score de similaridade."""

    score: float
    chunk: Chunk


@dataclass(frozen=True)
class WebReference:
    """Referência externa obtida em uma busca na internet."""

    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class Improvement:
    """Sugestão de melhoria para um trecho específico da petição."""

    trecho: str
    comentario: str
    categoria: str


@dataclass(frozen=True)
class ReviewResult:
    """Resultado da análise crítica de uma petição."""

    petition_path: str
    scores: dict[str, float]
    features: FeatureMap
    problems: list[str]
    suggestions: list[str]
    similar_chunks: list[SimilarChunk]
    markdown: str


@dataclass(frozen=True)
class RecreatedPetition:
    """Petição recriada com comentários inline e referências externas."""

    markdown: str
    web_references: list[WebReference]
    used_ollama: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScrapingCandidate:
    """Candidato a download obtido durante o web scraping."""

    url: str
    source_query: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class SavedDocument:
    """Documento aceito e armazenado pelo scraper."""

    file_name: str
    url: str
    source_query: str
    title: str
    score: int
    matched_terms: list[str]
    sha256: str
