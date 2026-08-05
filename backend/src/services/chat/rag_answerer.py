"""Estratégia de resposta com RAG: busca semântica na base + LLM."""

from __future__ import annotations

import re

from src.application.ports import ChatAnswerPort, ConversationalLLMPort
from src.application.use_cases.build_index import LoadOrBuildIndexUseCase
from src.config.settings import RagSettings
from src.domain.chat import (
    AnswerSource,
    ChatAnswer,
    ChatMessage,
    ChatRole,
    Citation,
    Intent,
)
from src.domain.entities import SimilarChunk
from src.infrastructure.nlp.case_outcome import outcome_label
from src.infrastructure.nlp.text_utils import short_excerpt
from src.services.chat.personas import get_persona
from src.services.chat.prompts import (
    RAG_USER_TEMPLATE,
    SYSTEM_RAG,
    resolve_persona_id,
    resolve_system_prompt,
    resolve_user_message,
)
from src.services.semantic_search import SemanticSearchService

# Modelos pequenos às vezes ecoam o contexto; removemos blocos estilo citação bruta.
_ECHOED_HEADER_RE = re.compile(
    r"(?im)^\s*\[\d+\]\s*(?:arquivo|file)\s*:.*$",
)


class RagAnswerer(ChatAnswerPort):
    """Recupera trechos relevantes da base e pede ao LLM uma resposta fundamentada."""

    intent = Intent.ASK_RAG

    def __init__(
        self,
        llm: ConversationalLLMPort,
        semantic_search: SemanticSearchService,
        load_or_build_index: LoadOrBuildIndexUseCase,
        rag_settings: RagSettings,
    ) -> None:
        self._llm = llm
        self._semantic_search = semantic_search
        self._load_or_build_index = load_or_build_index
        self._rag = rag_settings

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        try:
            chunks, _documents, embeddings = self._load_or_build_index.execute()
        except Exception as exc:  # noqa: BLE001 - falha de IO/index
            return ChatAnswer(
                text=(
                    "Não consegui carregar o índice RAG. Rode "
                    "`cd backend && python app.py index` ou clique em **Recriar índice RAG** "
                    f"na barra lateral. Detalhes: {exc}"
                ),
                source=AnswerSource.SYSTEM,
                intent=self.intent,
            )

        top_k = int(context.get("rag_top_k") or self._rag.top_k_similares)
        similar = self._semantic_search.search(
            query_text=user_message,
            chunks=chunks,
            embeddings=embeddings,
            top_k=top_k,
        )
        if not similar:
            return ChatAnswer(
                text="A base RAG não retornou trechos relevantes para a sua pergunta.",
                source=AnswerSource.RAG,
                intent=self.intent,
            )

        persona = get_persona(resolve_persona_id(context))
        rag_context = _format_chunks(similar)
        steered_question = resolve_user_message(user_message, context)
        user_prompt = RAG_USER_TEMPLATE.format(
            question=steered_question,
            context=rag_context,
        )
        text = self._llm.chat(
            [ChatMessage(role=ChatRole.USER, content=user_prompt)],
            system_prompt=resolve_system_prompt(SYSTEM_RAG, context),
            model=context.get("ollama_model"),
        )
        return ChatAnswer(
            text=_strip_echoed_chunks(text),
            source=AnswerSource.RAG,
            intent=self.intent,
            citations=[_to_citation(item) for item in similar],
            extra={
                "persona_id": persona.id,
                "persona_label": persona.label,
            },
        )


def _format_chunks(similar: list[SimilarChunk]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(similar, start=1):
        excerpt = short_excerpt(item.chunk.text, 900)
        features = item.chunk.features
        outcome = str(features.get("resultado", "indefinido"))
        action = str(features.get("tipo_acao", "geral"))
        subjects = str(features.get("assuntos", "nao_classificado"))
        blocks.append(
            f"Trecho {index} "
            f"(resultado: {outcome_label(outcome)}; "
            f"tipo: {action}; assuntos: {subjects}; "
            f"seção: {item.chunk.section}):\n{excerpt}"
        )
    return "\n\n".join(blocks)


def _strip_echoed_chunks(text: str) -> str:
    """Remove blocos em que o LLM colou metadados/trechos do contexto RAG."""
    if not _ECHOED_HEADER_RE.search(text) and "similaridade:" not in text.lower():
        return text.strip()

    # Mantém o texto antes do primeiro bloco ecoado.
    first_header = _ECHOED_HEADER_RE.search(text)
    intro = text[: first_header.start()].strip() if first_header else ""

    # E o fechamento sintético, se houver (ex.: "Em resumo...").
    summary_match = re.search(
        r"(?im)^(em resumo\b.*?)(?=^\s*\[\d+\]\s*(?:arquivo|file)\s*:|\Z)",
        text,
        flags=re.S,
    )
    summary = ""
    if summary_match:
        summary = _ECHOED_HEADER_RE.sub("", summary_match.group(1)).strip()
        summary = re.sub(r"\n{3,}", "\n\n", summary).strip()

    pieces = [part for part in (intro, summary) if part]
    return "\n\n".join(pieces) if pieces else text.strip()


def _to_citation(item: SimilarChunk) -> Citation:
    features = item.chunk.features
    outcome = str(features.get("resultado", "indefinido"))
    return Citation(
        title=item.chunk.file_name,
        detail=(
            f"Resultado: {outcome_label(outcome)} · "
            f"Seção: {item.chunk.section} · "
            f"Similaridade: {item.score:.3f}\n"
            f"{short_excerpt(item.chunk.text, 320)}"
        ),
    )
