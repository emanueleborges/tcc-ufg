"""Use case: analisar uma petição enviada comparando com o corpus."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.config.settings import RagSettings
from src.domain.entities import (
    Chunk,
    DocumentSummary,
    FeatureMap,
    ReviewResult,
    SimilarChunk,
)
from src.domain.validation import AnalysisTimeEntry
from src.infrastructure.persistence.analysis_time_repository_sqlite import (
    SQLiteAnalysisTimeRepository,
)
from src.services.benchmarks import BenchmarkMap, compute_corpus_benchmarks
from src.services.chunk_factory import ChunkFactory
from src.services.report_renderer import render_review_markdown
from src.services.scoring import score_review
from src.services.security.prompt_injection_analyzer import PromptInjectionAnalyzer
from src.services.semantic_search import SemanticSearchService

_FULL_TEXT_QUERY_LIMIT = 6000


class AnalyzePetitionUseCase:
    """Calcula scores, detecta problemas e sugere melhorias para a petição."""

    def __init__(
        self,
        chunk_factory: ChunkFactory,
        semantic_search: SemanticSearchService,
        rag_settings: RagSettings,
        prompt_injection_analyzer: PromptInjectionAnalyzer | None = None,
        analysis_time_repository: SQLiteAnalysisTimeRepository | None = None,
    ) -> None:
        self._chunk_factory = chunk_factory
        self._semantic_search = semantic_search
        self._rag = rag_settings
        self._injection_analyzer = prompt_injection_analyzer or PromptInjectionAnalyzer()
        self._analysis_times = analysis_time_repository

    def execute(
        self,
        petition_path: Path,
        chunks: list[Chunk],
        documents: list[DocumentSummary],
        embeddings: np.ndarray,
        *,
        record_time: bool = True,
        time_source: str = "auto",
    ) -> ReviewResult:
        started = time.perf_counter()
        petition_chunks, petition_summary = self._chunk_factory.build_for_pdf(petition_path)
        full_text = "\n\n".join(chunk.text for chunk in petition_chunks)
        injection = self._injection_analyzer.analyze_petition(
            text=full_text,
            pdf_path=petition_path,
        )
        features = petition_summary.features
        scores = score_review(features, documents)
        benchmarks = compute_corpus_benchmarks(documents)
        similar = self._semantic_search.search(
            query_text=full_text[:_FULL_TEXT_QUERY_LIMIT],
            chunks=chunks,
            embeddings=embeddings,
            top_k=self._rag.top_k_similares,
            exclude_document_id=petition_summary.document_id,
        )

        problems, suggestions = _detect_problems_and_suggestions(features, benchmarks)
        if injection.risk != "none":
            problems = [
                f"[Segurança] Possível injeção de prompt (risco {injection.risk}): "
                f"{injection.summary}",
                *problems,
            ]
            if injection.risk in {"high", "critical"}:
                suggestions = [
                    "Revise o PDF e remova trechos adversários antes de usar "
                    "este documento com LLMs.",
                    *suggestions,
                ]

        markdown = render_review_markdown(
            petition_path=str(petition_path),
            scores=scores,
            features=features,
            benchmarks=benchmarks,
            problems=problems,
            suggestions=suggestions,
            similar=similar,
        )
        if injection.risk != "none":
            markdown = (
                f"## Segurança — injeção de prompt\n\n"
                f"- **Risco:** `{injection.risk}`\n"
                f"- **Score:** {injection.score}/100\n"
                f"- {injection.summary}\n\n"
                + markdown
            )

        result = ReviewResult(
            petition_path=str(petition_path),
            scores=scores,
            features=features,
            problems=problems,
            suggestions=suggestions,
            similar_chunks=similar,
            markdown=markdown,
            prompt_injection=injection,
        )

        if record_time and self._analysis_times is not None:
            elapsed = time.perf_counter() - started
            self._analysis_times.save(
                AnalysisTimeEntry(
                    entry_id=uuid.uuid4().hex[:12],
                    petition_name=petition_path.name,
                    seconds=round(elapsed, 3),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    source=time_source,
                )
            )
        return result


def _detect_problems_and_suggestions(
    features: FeatureMap,
    benchmarks: BenchmarkMap,
) -> tuple[list[str], list[str]]:
    """Heurísticas para apontar fragilidades e sugerir melhorias."""
    problems: list[str] = []
    suggestions: list[str] = []

    if not features.get("tem_fatos"):
        problems.append("A narrativa dos fatos não foi identificada com clareza.")
        suggestions.append(
            "Crie uma seção objetiva de fatos, em ordem cronológica, "
            "conectando cada fato ao dano sofrido."
        )

    if not features.get("tem_fundamentacao"):
        problems.append(
            "A fundamentação jurídica parece superficial ou pouco sinalizada."
        )
        suggestions.append(
            "Inclua base legal expressa, responsabilidade civil, nexo causal, "
            "dano e culpa/risco, conforme o caso."
        )

    if not features.get("tem_pedidos"):
        problems.append("Os pedidos não foram identificados de forma robusta.")
        suggestions.append(
            "Separe pedidos em itens numerados, incluindo citação, procedência, "
            "condenação, juros, correção, custas e honorários."
        )

    juris_median = float(benchmarks.get("jurisprudencias", {}).get("mediana", 1))
    if int(features.get("jurisprudencias", 0) or 0) < juris_median:
        problems.append(
            "A quantidade de jurisprudência está abaixo da mediana das petições de referência."
        )
        suggestions.append(
            "Inclua precedentes recentes e conecte cada precedente ao ponto "
            "jurídico discutido."
        )

    provas_median = float(benchmarks.get("provas", {}).get("mediana", 1))
    if int(features.get("provas", 0) or 0) < provas_median:
        problems.append("A menção a provas/documentos está abaixo do padrão do corpus.")
        suggestions.append(
            "Explique quais documentos provam cada fato: prints, contratos, "
            "protocolos, laudos, comprovantes e testemunhas."
        )

    if not features.get("pedidos_subsidiarios"):
        suggestions.append(
            "Avalie incluir pedidos subsidiários ou sucessivos para aumentar "
            "a resiliência da tese."
        )

    if not features.get("valor_dano_moral"):
        suggestions.append(
            "Indique valor pretendido para dano moral e justifique proporcionalidade, "
            "razoabilidade e caráter pedagógico."
        )

    return problems, suggestions
