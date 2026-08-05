"""Busca semântica em cima dos embeddings indexados.

Além da similaridade vetorial, diversifica resultados entre casos
deferidos e indeferidos para expor padrões de êxito e de rejeição.
"""

from __future__ import annotations

import numpy as np

from src.application.ports import EmbeddingEnginePort
from src.domain.entities import Chunk, SimilarChunk


class SemanticSearchService:
    """Busca os chunks mais similares a uma query em texto livre."""

    def __init__(self, embedding_engine: EmbeddingEnginePort) -> None:
        self._engine = embedding_engine

    def search(
        self,
        query_text: str,
        chunks: list[Chunk],
        embeddings: np.ndarray,
        top_k: int,
        exclude_document_id: str | None = None,
    ) -> list[SimilarChunk]:
        if not chunks or embeddings.size == 0:
            return []
        query_vector = self._engine.encode_query(query_text)
        scores = np.dot(
            embeddings.astype("float64"),
            query_vector[0].astype("float64"),
        )
        preference = _outcome_preference(query_text)
        ordered_indices = np.argsort(scores)[::-1]

        ranked: list[SimilarChunk] = []
        for index in ordered_indices:
            chunk = chunks[index]
            if exclude_document_id and chunk.document_id == exclude_document_id:
                continue
            score = float(scores[index])
            outcome = str(chunk.features.get("resultado", "indefinido"))
            if preference == "deferido" and outcome == "deferido":
                score += 0.02
            elif preference == "indeferido" and outcome == "indeferido":
                score += 0.02
            elif preference == "parcial" and outcome == "parcial":
                score += 0.02
            ranked.append(SimilarChunk(score=score, chunk=chunk))

        ranked.sort(key=lambda item: item.score, reverse=True)
        return _diversify_by_outcome(ranked, top_k)


def _outcome_preference(query_text: str) -> str | None:
    lowered = query_text.lower()
    success_hints = (
        "êxito",
        "exito",
        "sucesso",
        "deferid",
        "procedente",
        "ganhar",
        "procedência",
        "procedencia",
    )
    failure_hints = (
        "indeferid",
        "improcedente",
        "rejeit",
        "perda",
        "desprovido",
        "improcedência",
        "improcedencia",
    )
    partial_hints = (
        "parcial",
        "parcialmente procedente",
        "provimento parcial",
        "procedência parcial",
        "procedencia parcial",
    )
    if any(hint in lowered for hint in partial_hints):
        return "parcial"
    if any(hint in lowered for hint in success_hints):
        return "deferido"
    if any(hint in lowered for hint in failure_hints):
        return "indeferido"
    return None


def _diversify_by_outcome(
    ranked: list[SimilarChunk],
    top_k: int,
) -> list[SimilarChunk]:
    """Prioriza contraste deferido/indeferido sem perder relevância semântica."""
    if top_k <= 1 or len(ranked) <= top_k:
        return ranked[:top_k]

    selected: list[SimilarChunk] = []
    selected_ids: set[str] = set()

    def _take(predicate) -> None:
        for item in ranked:
            if len(selected) >= top_k:
                return
            key = item.chunk.chunk_id
            if key in selected_ids:
                continue
            if predicate(item):
                selected.append(item)
                selected_ids.add(key)

    # Garante pelo menos um de cada polo, se existir no ranking amplo.
    _take(lambda item: str(item.chunk.features.get("resultado")) == "deferido")
    _take(lambda item: str(item.chunk.features.get("resultado")) == "indeferido")
    _take(lambda item: str(item.chunk.features.get("resultado")) == "parcial")
    # Completa com os melhores restantes.
    _take(lambda _item: True)
    selected.sort(key=lambda item: item.score, reverse=True)
    return selected[:top_k]
