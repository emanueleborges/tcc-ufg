"""Use case: baixar PDFs públicos para alimentar a base RAG."""

from __future__ import annotations

from src.infrastructure.scraping.pdf_scraper import PdfScraper


class DownloadPetitionsUseCase:
    """Wrapper de aplicação para o scraper de PDFs."""

    def __init__(self, scraper: PdfScraper) -> None:
        self._scraper = scraper

    def execute(self) -> int:
        return self._scraper.run()
