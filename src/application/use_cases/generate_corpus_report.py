"""Use case: gerar relatório markdown do corpus indexado."""

from __future__ import annotations

from pathlib import Path

from src.config.settings import PathsSettings
from src.domain.entities import Chunk, DocumentSummary
from src.services.report_renderer import render_corpus_report


class GenerateCorpusReportUseCase:
    """Gera e persiste o relatório agregado da base RAG."""

    REPORT_FILE_NAME = "relatorio_base_rag.md"

    def __init__(self, paths: PathsSettings) -> None:
        self._paths = paths

    def execute(
        self,
        documents: list[DocumentSummary],
        chunks: list[Chunk],
    ) -> Path:
        self._paths.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self._paths.reports_dir / self.REPORT_FILE_NAME
        report_path.write_text(
            render_corpus_report(documents, chunks),
            encoding="utf-8",
        )
        return report_path
