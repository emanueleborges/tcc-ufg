"""Estratégia de resposta com RAG: busca semântica na base + LLM."""

from __future__ import annotations

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
from src.infrastructure.nlp.text_utils import short_excerpt
from src.services.chat.prompts import RAG_USER_TEMPLATE, SYSTEM_RAG
from src.services.semantic_search import SemanticSearchService


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
                    "`python app.py index` ou clique em **Recriar índice RAG** "
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

        rag_context = _format_chunks(similar)
        user_prompt = RAG_USER_TEMPLATE.format(question=user_message, context=rag_context)
        text = self._llm.chat(
            [ChatMessage(role=ChatRole.USER, content=user_prompt)],
            system_prompt=SYSTEM_RAG,
            model=context.get("ollama_model"),
        )
        return ChatAnswer(
            text=text,
            source=AnswerSource.RAG,
            intent=self.intent,
            citations=[_to_citation(item) for item in similar],
        )


def _format_chunks(similar: list[SimilarChunk]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(similar, start=1):
        excerpt = short_excerpt(item.chunk.text, 900)
        blocks.append(
            f"[{index}] arquivo: {item.chunk.file_name} | seção: {item.chunk.section} "
            f"| similaridade: {item.score:.3f}\n{excerpt}"
        )
    return "\n\n".join(blocks)


def _to_citation(item: SimilarChunk) -> Citation:
    return Citation(
        title=item.chunk.file_name,
        detail=(
            f"Seção: {item.chunk.section} · "
            f"Similaridade: {item.score:.3f}\n"
            f"{short_excerpt(item.chunk.text, 320)}"
        ),
    )
