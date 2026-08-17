"""Persistência do índice RAG em ChromaDB (banco vetorial).

Coleção ``peticoes_chunks``: cada chunk vira um registro com
``id = chunk_id``, ``document = texto``, ``embedding`` e metadados
(features serializadas em JSON + ``row_index`` para alinhar a matriz
na leitura). Os ``DocumentSummary`` (agregados sem vetor) seguem em
``documentos.json`` ao lado do diretório do Chroma.

Na primeira execução, migra automaticamente o formato legado
(``chunks.jsonl`` + ``embeddings.npy``) para a coleção, sem rebuild.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from src.application.ports import IndexRepositoryPort
from src.domain.entities import Chunk, DocumentSummary
from src.infrastructure.persistence.index_repository import FileSystemIndexRepository

if TYPE_CHECKING:
    import chromadb

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


class ChromaIndexRepository(IndexRepositoryPort):
    """Implementa ``IndexRepositoryPort`` usando ChromaDB persistente."""

    COLLECTION_NAME = "peticoes_chunks"
    DOCUMENTS_FILE = "documentos.json"
    CHROMA_DIR = "chroma"

    def __init__(self, index_dir: Path) -> None:
        self._index_dir = index_dir
        self._legacy = FileSystemIndexRepository(index_dir)
        self._migration_checked = False

    @property
    def documents_path(self) -> Path:
        return self._index_dir / self.DOCUMENTS_FILE

    # ----- infra interna -----

    def _client(self) -> "chromadb.PersistentClient":
        import chromadb

        chroma_dir = self._index_dir / self.CHROMA_DIR
        chroma_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(chroma_dir))

    def _collection(self, client: "chromadb.PersistentClient"):
        return client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _chunk_metadata(row_index: int, chunk: Chunk) -> dict[str, Any]:
        return {
            "document_id": chunk.document_id,
            "file_name": chunk.file_name,
            "section": chunk.section,
            "page_start": int(chunk.page_start),
            "page_end": int(chunk.page_end),
            "features": json.dumps(chunk.features, ensure_ascii=False),
            "row_index": row_index,
        }

    def _migrate_legacy_if_needed(self) -> None:
        """Importa o índice filesystem+NumPy para o ChromaDB uma única vez."""
        if self._migration_checked:
            return
        self._migration_checked = True
        collection = self._collection(self._client())
        if collection.count() > 0 or not self._legacy.exists():
            return
        chunks, documents, embeddings = self._legacy.load()
        self.save(chunks, documents, embeddings)
        logger.info(
            "Índice legado migrado para ChromaDB: %d chunks / %d documentos.",
            len(chunks),
            len(documents),
        )

    # ----- IndexRepositoryPort -----

    def exists(self) -> bool:
        self._migrate_legacy_if_needed()
        collection = self._collection(self._client())
        return collection.count() > 0 and self.documents_path.exists()

    def save(
        self,
        chunks: list[Chunk],
        documents: list[DocumentSummary],
        embeddings: np.ndarray,
    ) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        client = self._client()
        existing = {collection.name for collection in client.list_collections()}
        if self.COLLECTION_NAME in existing:
            client.delete_collection(self.COLLECTION_NAME)
        collection = self._collection(client)

        for start in range(0, len(chunks), _BATCH_SIZE):
            end = min(start + _BATCH_SIZE, len(chunks))
            batch = chunks[start:end]
            collection.add(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=[
                    embeddings[row].astype("float32").tolist()
                    for row in range(start, end)
                ],
                metadatas=[
                    self._chunk_metadata(row, chunk)
                    for row, chunk in enumerate(batch, start=start)
                ],
            )

        self.documents_path.write_text(
            json.dumps([asdict(doc) for doc in documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> tuple[list[Chunk], list[DocumentSummary], np.ndarray]:
        self._migrate_legacy_if_needed()
        collection = self._collection(self._client())
        if collection.count() == 0 or not self.documents_path.exists():
            raise FileNotFoundError(
                f"Índice RAG não encontrado em {self._index_dir}. "
                "Rode o comando de indexação antes."
            )

        result = collection.get(include=["documents", "metadatas", "embeddings"])
        rows = sorted(
            zip(
                result["ids"],
                result["documents"] or [],
                result["metadatas"] or [],
                result["embeddings"] if result["embeddings"] is not None else [],
            ),
            key=lambda row: int(row[2]["row_index"]),
        )
        chunks = [
            Chunk(
                chunk_id=chunk_id,
                document_id=str(metadata["document_id"]),
                file_name=str(metadata["file_name"]),
                section=str(metadata["section"]),
                text=text,
                page_start=int(metadata["page_start"]),
                page_end=int(metadata["page_end"]),
                features=json.loads(str(metadata["features"])),
            )
            for chunk_id, text, metadata, _embedding in rows
        ]
        embeddings = np.asarray(
            [row[3] for row in rows], dtype="float32"
        )
        documents = [
            DocumentSummary(**row)
            for row in json.loads(self.documents_path.read_text(encoding="utf-8"))
        ]
        return chunks, documents, embeddings
