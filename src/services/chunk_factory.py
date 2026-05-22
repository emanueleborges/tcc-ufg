"""Constrói chunks e resumo agregado a partir de um PDF jurídico."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.application.ports import PdfReaderPort
from src.config.settings import RagSettings
from src.domain.entities import Chunk, DocumentSummary
from src.infrastructure.nlp.chunking import split_paragraph_chunks
from src.infrastructure.nlp.feature_extractor import extract_features
from src.infrastructure.nlp.section_detector import detect_section
from src.infrastructure.nlp.text_utils import anonymize_text


class ChunkFactory:
    """Fábrica de chunks + summary para um PDF de petição."""

    def __init__(self, pdf_reader: PdfReaderPort, rag_settings: RagSettings) -> None:
        self._pdf_reader = pdf_reader
        self._rag = rag_settings

    def build_for_pdf(self, path: Path) -> tuple[list[Chunk], DocumentSummary]:
        pages = self._pdf_reader.read_pages(path)
        document_id = path.stem
        all_text = "\n\n".join(pages)
        if self._rag.anonymize:
            all_text = anonymize_text(all_text)

        raw_chunks = split_paragraph_chunks(
            all_text,
            max_chars=self._rag.max_chunk_chars,
            min_chars=self._rag.min_chunk_chars,
        )

        chunks: list[Chunk] = []
        section_counter: Counter[str] = Counter()
        for index, chunk_text in enumerate(raw_chunks):
            section = detect_section(chunk_text)
            section_counter[section] += 1
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:{index:04d}",
                    document_id=document_id,
                    file_name=path.name,
                    section=section,
                    text=chunk_text,
                    page_start=1,
                    page_end=len(pages),
                    features=extract_features(chunk_text),
                )
            )
        summary = DocumentSummary(
            document_id=document_id,
            file_name=path.name,
            path=str(path),
            chars=len(all_text),
            chunks=len(chunks),
            sections=dict(section_counter),
            features=extract_features(all_text),
        )
        return chunks, summary
