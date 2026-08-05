"""Use case: baixar PDFs públicos para alimentar a base RAG."""

from __future__ import annotations

from collections.abc import Callable

from src.domain.entities import ScrapingResult
from src.infrastructure.scraping.pdf_scraper import PdfScraper

ProgressCallback = Callable[[int, str], None]


class DownloadPetitionsUseCase:
    """Wrapper de aplicação para o scraper de PDFs."""

    def __init__(self, scraper: PdfScraper) -> None:
        self._scraper = scraper

    def execute(self, on_progress: ProgressCallback | None = None) -> ScrapingResult:
        return self._scraper.run(on_progress=on_progress)
