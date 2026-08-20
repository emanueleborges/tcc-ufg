"""Adapter de embeddings baseado em SentenceTransformer."""

from __future__ import annotations

import logging
import os
import sys
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable

import numpy as np

from src.application.ports import EmbeddingEnginePort

if TYPE_CHECKING:  # carga preguiçosa: evita exigir sentence-transformers no import-time
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> "SentenceTransformer":
    """Carrega o modelo uma única vez por nome (cache em memória).

    Se o Hugging Face Hub estiver inacessível (rede restrita/proxy), cai para
    o cache local do modelo em vez de falhar.
    """
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "HF Hub inacessível (%s); carregando modelo do cache local.", exc
        )
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        return SentenceTransformer(model_name, local_files_only=True)


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vectors / norms


def _with_prefix(texts: Iterable[str], prefix: str) -> list[str]:
    return [prefix + text.replace("\n", " ") for text in texts]


class SentenceTransformerEmbeddingEngine(EmbeddingEnginePort):
    """Implementação concreta de ``EmbeddingEnginePort`` usando E5."""

    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        self._model_name = model_name
        self._batch_size = batch_size

    @property
    def _model(self) -> "SentenceTransformer":
        return _load_model(self._model_name)

    def encode_passages(self, texts: Iterable[str]) -> np.ndarray:
        prepared = _with_prefix(texts, _PASSAGE_PREFIX)
        if not prepared:
            return np.empty((0,), dtype="float32")
        is_streamlit = "streamlit" in sys.modules
        embeddings = self._model.encode(
            prepared,
            batch_size=self._batch_size,
            show_progress_bar=not is_streamlit,
            convert_to_numpy=True,
        )
        return _normalize_vectors(embeddings.astype("float32"))

    def encode_query(self, text: str) -> np.ndarray:
        prepared = _with_prefix([text], _QUERY_PREFIX)
        embedding = self._model.encode(prepared, convert_to_numpy=True).astype("float32")
        return _normalize_vectors(embedding)
