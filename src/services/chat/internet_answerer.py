"""Estratégia de resposta com busca na internet (DuckDuckGo) + LLM."""

from __future__ import annotations

from src.application.ports import ChatAnswerPort, ConversationalLLMPort, WebSearchPort
from src.config.settings import WebSearchSettings
from src.domain.chat import (
    AnswerSource,
    ChatAnswer,
    ChatMessage,
    ChatRole,
    Citation,
    Intent,
)
from src.domain.entities import WebReference
from src.infrastructure.nlp.text_utils import short_excerpt
from src.services.chat.prompts import INTERNET_USER_TEMPLATE, SYSTEM_INTERNET


class InternetAnswerer(ChatAnswerPort):
    """Busca na web via DuckDuckGo e sintetiza a resposta com o LLM."""

    intent = Intent.ASK_INTERNET

    def __init__(
        self,
        llm: ConversationalLLMPort,
        web_search: WebSearchPort,
        web_search_settings: WebSearchSettings,
    ) -> None:
        self._llm = llm
        self._web_search = web_search
        self._settings = web_search_settings

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        max_results = int(context.get("web_max_results") or self._settings.max_results)
        try:
            references = self._web_search.search_text(user_message, max_results)
        except Exception as exc:  # noqa: BLE001 - falha de rede/rate limit
            return ChatAnswer(
                text=(
                    "Falha ao consultar a internet (DuckDuckGo). "
                    f"Tente novamente. Detalhes: {exc}"
                ),
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )
        if not references:
            return ChatAnswer(
                text="Não encontrei resultados relevantes na internet para essa pergunta.",
                source=AnswerSource.INTERNET,
                intent=self.intent,
            )

        web_context = _format_references(references)
        user_prompt = INTERNET_USER_TEMPLATE.format(
            question=user_message, context=web_context
        )
        text = self._llm.chat(
            [ChatMessage(role=ChatRole.USER, content=user_prompt)],
            system_prompt=SYSTEM_INTERNET,
            model=context.get("ollama_model"),
        )
        return ChatAnswer(
            text=text,
            source=AnswerSource.INTERNET,
            intent=self.intent,
            citations=[_to_citation(ref) for ref in references],
        )


def _format_references(references: list[WebReference]) -> str:
    blocks: list[str] = []
    for index, reference in enumerate(references, start=1):
        snippet = short_excerpt(reference.snippet, 500) if reference.snippet else ""
        blocks.append(
            f"[{index}] {reference.title}\nURL: {reference.url}\nResumo: {snippet}"
        )
    return "\n\n".join(blocks)


def _to_citation(reference: WebReference) -> Citation:
    return Citation(
        title=reference.title or reference.url,
        detail=short_excerpt(reference.snippet, 320) if reference.snippet else "",
        url=reference.url,
    )
