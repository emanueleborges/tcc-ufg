"""Leitor de PDF com fallback de OCR (implementa ``PdfReaderPort``)."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader as _PdfReader

from src.application.ports import PdfReaderPort
from src.infrastructure.nlp.text_utils import has_enough_text, normalize_text
from src.infrastructure.pdf.ocr_engine import ocr_missing_pages


class PdfReader(PdfReaderPort):
    """Lê páginas de PDFs, executando OCR quando o texto nativo é insuficiente."""

    def read_pages(self, path: Path) -> list[str]:
        reader = _PdfReader(str(path))
        native_pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
        if all(has_enough_text(text) for text in native_pages):
            return native_pages
        return ocr_missing_pages(path, native_pages)

    def read_text(self, path: Path) -> str:
        pages = self.read_pages(path)
        return "\n\n".join(page for page in pages if page.strip()).strip()
