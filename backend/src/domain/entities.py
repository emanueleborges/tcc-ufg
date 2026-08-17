"""Entidades de domínio do crítico jurídico.

Estruturas de dados puras (dataclasses) sem dependências externas.
São o coração do sistema e podem ser usadas por qualquer camada.
"""

from __future__ import annotations

from dataclasses import dataclass
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
class PromptInjectionFinding:
    """Indício de possível injeção de prompt no texto da petição."""

    pattern_id: str
    severity: str
    description: str
    excerpt: str
    matched: str
    owasp_categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptInjectionReport:
    """Resultado da varredura de injeção de prompt (alinhado ao OWASP LLM Top 10)."""

    risk: str
    score: int
    summary: str
    findings: list[PromptInjectionFinding]
    scanned_chars: int = 0
    # OWASP Top 10 for LLM Applications 2025
    owasp_id: str = "LLM01:2025"
    owasp_name: str = "Prompt Injection"
    owasp_url: str = "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"
    attack_types: tuple[str, ...] = ()
    techniques: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()
    verdict: str = "clean"  # clean | suspicious | malicious


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
    prompt_injection: PromptInjectionReport | None = None


@dataclass(frozen=True)
class ScrapingResult:
    """Resumo de uma execução do scraper."""

    total_documents: int
    new_accepted: int
    new_rejected: int
    new_partial: int
    candidates_found: int
    message: str


@dataclass(frozen=True)
class ScrapingCandidate:
    """Candidato a download obtido durante o web scraping."""

    url: str
    source_query: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class SavedDocument:
    """Documento baixado e armazenado pelo scraper (aceito ou rejeitado)."""

    file_name: str
    url: str
    source_query: str
    title: str
    score: int
    matched_terms: list[str]
    sha256: str
    outcome: str = "indefinido"
    status: str = "aceita"  # aceita | rejeitada | parcial
