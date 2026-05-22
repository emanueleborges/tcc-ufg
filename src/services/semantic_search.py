"""Busca semântica em cima dos embeddings indexados."""

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
        ordered_indices = np.argsort(scores)[::-1]
        similar: list[SimilarChunk] = []
        for index in ordered_indices:
            chunk = chunks[index]
            if exclude_document_id and chunk.document_id == exclude_document_id:
                continue
            similar.append(SimilarChunk(score=float(scores[index]), chunk=chunk))
            if len(similar) >= top_k:
                break
        return similar
