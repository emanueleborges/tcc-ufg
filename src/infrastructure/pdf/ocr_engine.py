"""OCR de páginas PDF via RapidOCR 3.x (lazy load).

Compatível com a API ``RapidOCROutput`` do pacote ``rapidocr`` (sucessor
do antigo ``rapidocr-onnxruntime``), que expõe ``.txts``, ``.boxes`` e
``.scores`` em vez do retorno legado ``(result, elapsed)``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from src.infrastructure.nlp.text_utils import has_enough_text, normalize_text


@lru_cache(maxsize=1)
def _get_ocr_engine():
    """Carrega o engine OCR apenas quando necessário (lazy)."""
    from rapidocr import RapidOCR

    return RapidOCR()


def _ocr_page(page) -> str:
    """Roda OCR em uma página do PyMuPDF e retorna texto normalizado."""
    import fitz

    matrix = fitz.Matrix(2, 2)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    result = _get_ocr_engine()(image)
    txts = getattr(result, "txts", None) or ()
    lines = [str(line).strip() for line in txts if str(line).strip()]
    if not lines:
        return ""
    return normalize_text("\n".join(lines))


def ocr_missing_pages(path: Path, native_pages: list[str]) -> list[str]:
    """Aplica OCR apenas em páginas com texto nativo insuficiente."""
    import fitz

    ocr_pages = native_pages.copy()
    with fitz.open(str(path)) as document:
        for index, page in enumerate(document):
            native_text = native_pages[index] if index < len(native_pages) else ""
            if has_enough_text(native_text):
                continue
            try:
                ocr_text = _ocr_page(page)
            except Exception:  # noqa: BLE001 - OCR pode falhar em PDFs corrompidos
                ocr_text = ""
            if len(ocr_text) > len(native_text):
                ocr_pages[index] = ocr_text
    return ocr_pages
