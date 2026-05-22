"""Use case: recriar a petição mantendo o original com comentários inline."""

from __future__ import annotations

from pathlib import Path

from src.application.ports import LLMClientPort, PdfReaderPort, WebSearchPort
from src.config.settings import WebSearchSettings
from src.domain.entities import Improvement, RecreatedPetition, ReviewResult, WebReference
from src.services.inline_comments import insert_inline_comments
from src.services.report_renderer import render_recreated_markdown


class RecreatePetitionUseCase:
    """Gera a petição recriada com comentários inline produzidos pelo LLM."""

    def __init__(
        self,
        pdf_reader: PdfReaderPort,
        llm_client: LLMClientPort,
        web_search: WebSearchPort,
        web_search_settings: WebSearchSettings,
    ) -> None:
        self._pdf_reader = pdf_reader
        self._llm_client = llm_client
        self._web_search = web_search
        self._web_search_settings = web_search_settings

    def execute(
        self,
        petition_path: Path,
        review: ReviewResult,
        *,
        use_internet: bool,
        use_ollama: bool,
        ollama_model: str,
    ) -> RecreatedPetition:
        original_text = self._pdf_reader.read_text(petition_path)
        warnings: list[str] = []
        if not original_text:
            warnings.append(
                "Não foi possível extrair texto útil do PDF. A recriação integral "
                "depende de um PDF com texto selecionável ou OCR funcional."
            )
            original_text = "[Não foi possível extrair o texto integral da petição enviada.]"

        web_references = self._collect_web_references(review, use_internet)

        improvements: list[Improvement] = []
        unmatched: list[Improvement] = []
        annotated_text = original_text
        used_ollama = False

        if use_ollama:
            improvements, unmatched, annotated_text, ollama_warnings, used_ollama = (
                self._generate_improvements(
                    original_text=original_text,
                    review=review,
                    web_references=web_references,
                    model=ollama_model,
                )
            )
            warnings.extend(ollama_warnings)
        else:
            warnings.append(
                "Ollama não foi usado. A saída preserva a petição original extraída "
                "do PDF, sem comentários automáticos."
            )

        markdown = render_recreated_markdown(
            original_text=original_text,
            annotated_text=annotated_text,
            improvements=improvements,
            unmatched=unmatched,
            web_references=web_references,
            used_ollama=used_ollama,
        )
        return RecreatedPetition(
            markdown=markdown,
            web_references=web_references,
            used_ollama=used_ollama,
            warnings=warnings,
        )

    def _collect_web_references(
        self, review: ReviewResult, use_internet: bool
    ) -> list[WebReference]:
        if not use_internet:
            return []
        return self._web_search.search_references(
            review, self._web_search_settings.max_results
        )

    def _generate_improvements(
        self,
        *,
        original_text: str,
        review: ReviewResult,
        web_references: list[WebReference],
        model: str,
    ) -> tuple[list[Improvement], list[Improvement], str, list[str], bool]:
        warnings: list[str] = []
        try:
            improvements = self._llm_client.generate_improvements(
                original_text=original_text,
                review=review,
                web_references=web_references,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001 - falha do LLM não deve quebrar o fluxo
            warnings.append(
                f"Ollama indisponível ou falhou: {exc}. Mantida a petição original "
                "sem comentários automáticos."
            )
            return [], [], original_text, warnings, False

        if not improvements:
            warnings.append(
                "O Ollama não retornou melhorias. Mantida a petição original sem comentários."
            )
            return [], [], original_text, warnings, True

        annotated_text, unmatched = insert_inline_comments(original_text, improvements)
        return improvements, unmatched, annotated_text, warnings, True
