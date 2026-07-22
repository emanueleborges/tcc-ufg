"""Persistência do índice RAG em sistema de arquivos."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from src.application.ports import IndexRepositoryPort
from src.domain.entities import Chunk, DocumentSummary


class FileSystemIndexRepository(IndexRepositoryPort):
    """Salva/carrega o índice RAG em três arquivos:

    - ``chunks.jsonl``: um chunk por linha (JSON)
    - ``documentos.json``: lista de DocumentSummary
    - ``embeddings.npy``: matriz numpy
    """

    CHUNKS_FILE = "chunks.jsonl"
    DOCUMENTS_FILE = "documentos.json"
    EMBEDDINGS_FILE = "embeddings.npy"

    def __init__(self, index_dir: Path) -> None:
        self._index_dir = index_dir

    @property
    def chunks_path(self) -> Path:
        return self._index_dir / self.CHUNKS_FILE

    @property
    def documents_path(self) -> Path:
        return self._index_dir / self.DOCUMENTS_FILE

    @property
    def embeddings_path(self) -> Path:
        return self._index_dir / self.EMBEDDINGS_FILE

    def exists(self) -> bool:
        return (
            self.chunks_path.exists()
            and self.documents_path.exists()
            and self.embeddings_path.exists()
        )

    def save(
        self,
        chunks: list[Chunk],
        documents: list[DocumentSummary],
        embeddings: np.ndarray,
    ) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        with self.chunks_path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
        self.documents_path.write_text(
            json.dumps([asdict(doc) for doc in documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        np.save(self.embeddings_path, embeddings)

    def load(self) -> tuple[list[Chunk], list[DocumentSummary], np.ndarray]:
        if not self.exists():
            raise FileNotFoundError(
                f"Índice RAG não encontrado em {self._index_dir}. "
                "Rode o comando de indexação antes."
            )
        chunks: list[Chunk] = []
        with self.chunks_path.open("r", encoding="utf-8") as file:
            for line in file:
                chunks.append(Chunk(**json.loads(line)))
        documents = [
            DocumentSummary(**row)
            for row in json.loads(self.documents_path.read_text(encoding="utf-8"))
        ]
        embeddings = np.load(self.embeddings_path)
        return chunks, documents, embeddings
