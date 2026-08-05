"""Estratégias que delegam aos use cases já existentes de análise/recriação."""

from __future__ import annotations

from pathlib import Path

from src.application.ports import ChatAnswerPort
from src.application.use_cases.analyze_petition import AnalyzePetitionUseCase
from src.application.use_cases.build_index import LoadOrBuildIndexUseCase
from src.application.use_cases.recreate_petition import RecreatePetitionUseCase
from src.domain.chat import (
    AnswerSource,
    ChatAnswer,
    ChatMessage,
    Citation,
    Intent,
)
from src.infrastructure.nlp.case_outcome import outcome_label
from src.infrastructure.nlp.text_utils import short_excerpt


class AnalyzePetitionAnswerer(ChatAnswerPort):
    """Aciona o use case de análise crítica quando o usuário pede para avaliar."""

    intent = Intent.ANALYZE_PETITION

    def __init__(
        self,
        load_or_build_index: LoadOrBuildIndexUseCase,
        analyze_petition: AnalyzePetitionUseCase,
    ) -> None:
        self._load_or_build_index = load_or_build_index
        self._analyze_petition = analyze_petition

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        petition_path_value = context.get("petition_path")
        if not petition_path_value:
            return ChatAnswer(
                text=(
                    "Para analisar uma petição, anexe um PDF no painel lateral "
                    "antes de pedir a análise."
                ),
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )

        try:
            chunks, documents, embeddings = self._load_or_build_index.execute()
            review = self._analyze_petition.execute(
                petition_path=Path(petition_path_value),
                chunks=chunks,
                documents=documents,
                embeddings=embeddings,
            )
        except Exception as exc:  # noqa: BLE001
            return ChatAnswer(
                text=f"Não consegui analisar a petição. Detalhes: {exc}",
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )

        return ChatAnswer(
            text=_analysis_message(review),
            source=AnswerSource.PETITION_ANALYSIS,
            intent=self.intent,
            citations=[
                Citation(
                    title=item.chunk.file_name,
                    detail=(
                        f"Resultado: {outcome_label(str(item.chunk.features.get('resultado', 'indefinido')))} · "
                        f"Seção: {item.chunk.section} · Sim: {item.score:.3f}\n"
                        f"{short_excerpt(item.chunk.text, 280)}"
                    ),
                )
                for item in review.similar_chunks[:5]
            ],
            extra={"review": review},
        )


def _analysis_message(review) -> str:
    injection = getattr(review, "prompt_injection", None)
    base = "Análise concluída. Os detalhes estão no painel abaixo."
    if injection is None or injection.risk == "none":
        return (
            f"{base} Varredura de injeção de prompt: nenhum indício relevante."
        )
    alert = (
        f"⚠️ Segurança: possível injeção de prompt (risco **{injection.risk}**, "
        f"score {injection.score}/100). {injection.summary}"
    )
    if injection.blocked_for_llm:
        alert += (
            " A recriação com LLM ficará bloqueada até o documento ser limpo."
        )
    return f"{base}\n\n{alert}"


class RecreatePetitionAnswerer(ChatAnswerPort):
    """Aciona o use case de recriação quando o usuário pede para melhorar/recriar."""

    intent = Intent.RECREATE_PETITION

    def __init__(
        self,
        load_or_build_index: LoadOrBuildIndexUseCase,
        analyze_petition: AnalyzePetitionUseCase,
        recreate_petition: RecreatePetitionUseCase,
    ) -> None:
        self._load_or_build_index = load_or_build_index
        self._analyze_petition = analyze_petition
        self._recreate_petition = recreate_petition

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        petition_path_value = context.get("petition_path")
        if not petition_path_value:
            return ChatAnswer(
                text=(
                    "Para recriar uma petição, anexe um PDF no painel lateral "
                    "antes de pedir a recriação."
                ),
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )

        try:
            chunks, documents, embeddings = self._load_or_build_index.execute()
            review = self._analyze_petition.execute(
                petition_path=Path(petition_path_value),
                chunks=chunks,
                documents=documents,
                embeddings=embeddings,
            )
            injection = review.prompt_injection
            if injection is not None and injection.blocked_for_llm:
                return ChatAnswer(
                    text=(
                        "Recriação bloqueada por segurança.\n\n"
                        f"A petição anexada apresentou risco **{injection.risk}** "
                        f"de injeção de prompt (score {injection.score}/100). "
                        f"{injection.summary}\n\n"
                        "Remova trechos adversários do PDF e peça a análise novamente "
                        "antes de recriar com o LLM."
                    ),
                    source=AnswerSource.SYSTEM,
                    intent=self.intent,
                    extra={"review": review},
                )
            recreated = self._recreate_petition.execute(
                petition_path=Path(petition_path_value),
                review=review,
                use_internet=bool(context.get("use_internet", True)),
                use_ollama=True,
                ollama_model=str(context.get("ollama_model") or "llama3.1:8b"),
            )
        except Exception as exc:  # noqa: BLE001
            return ChatAnswer(
                text=f"Não consegui recriar a petição. Detalhes: {exc}",
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )

        return ChatAnswer(
            text=(
                "Petição recriada com comentários inline. Veja o documento completo no "
                "painel da direita ou baixe o PDF gerado em `relatorios/`."
            ),
            source=AnswerSource.PETITION_RECREATION,
            intent=self.intent,
            citations=[
                Citation(
                    title=ref.title or ref.url,
                    detail=short_excerpt(ref.snippet, 280) if ref.snippet else "",
                    url=ref.url,
                )
                for ref in recreated.web_references
            ],
            extra={"recreated": recreated, "review": review},
        )
