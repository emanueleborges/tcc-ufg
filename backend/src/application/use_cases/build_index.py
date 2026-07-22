"""Construção e carregamento do índice RAG jurídico."""

from __future__ import annotations

import sys
from collections.abc import Callable

import numpy as np
from tqdm import tqdm

from src.application.ports import EmbeddingEnginePort, IndexRepositoryPort
from src.config.settings import PathsSettings
from src.domain.entities import Chunk, DocumentSummary
from src.services.chunk_factory import ChunkFactory

IndexTuple = tuple[list[Chunk], list[DocumentSummary], np.ndarray]
ProgressCallback = Callable[[int, str], None]


class BuildIndexUseCase:
    """Indexa todos os PDFs aceitos e persiste o índice em disco."""

    def __init__(
        self,
        chunk_factory: ChunkFactory,
        embedding_engine: EmbeddingEnginePort,
        index_repository: IndexRepositoryPort,
        paths: PathsSettings,
    ) -> None:
        self._chunk_factory = chunk_factory
        self._embedding_engine = embedding_engine
        self._index_repository = index_repository
        self._paths = paths

    def execute(self, on_progress: ProgressCallback | None = None) -> IndexTuple:
        def report(percent: int, message: str) -> None:
            if on_progress:
                on_progress(max(0, min(100, percent)), message)

        report(1, "Listando PDFs aceitos…")
        pdfs = sorted(self._paths.accepted_pdfs_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError(
                f"Nenhum PDF encontrado em {self._paths.accepted_pdfs_dir}. "
                "Rode o comando de scraping primeiro."
            )

        all_chunks: list[Chunk] = []
        documents: list[DocumentSummary] = []
        is_streamlit = "streamlit" in sys.modules
        total = len(pdfs)
        for index, path in enumerate(
            tqdm(pdfs, desc="Extraindo PDFs", disable=is_streamlit)
        ):
            percent = 5 + int((index / max(total, 1)) * 70)
            report(percent, f"Extraindo {path.name} ({index + 1}/{total})")
            try:
                chunks, summary = self._chunk_factory.build_for_pdf(path)
            except Exception as exc:  # noqa: BLE001
                print(f"Aviso: falha ao processar {path.name}: {exc}")
                continue
            if chunks:
                all_chunks.extend(chunks)
                documents.append(summary)

        if not all_chunks:
            raise RuntimeError("Nenhum texto útil foi extraído dos PDFs.")

        report(78, "Gerando embeddings…")
        embeddings = self._embedding_engine.encode_passages(
            chunk.text for chunk in all_chunks
        )
        report(92, "Salvando índice em disco…")
        self._index_repository.save(all_chunks, documents, embeddings)
        report(100, "Índice recriado.")
        return all_chunks, documents, embeddings


class LoadOrBuildIndexUseCase:
    """Carrega o índice existente ou força a sua reconstrução se ausente."""

    def __init__(
        self,
        index_repository: IndexRepositoryPort,
        build_index_use_case: BuildIndexUseCase,
    ) -> None:
        self._index_repository = index_repository
        self._build_index = build_index_use_case

    def execute(self) -> IndexTuple:
        if self._index_repository.exists():
            return self._index_repository.load()
        return self._build_index.execute()
