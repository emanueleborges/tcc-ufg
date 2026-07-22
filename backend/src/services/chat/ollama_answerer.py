"""Estratégia de resposta direta via Ollama (chat geral)."""

from __future__ import annotations

from src.application.ports import ChatAnswerPort, ConversationalLLMPort
from src.domain.chat import AnswerSource, ChatAnswer, ChatMessage, ChatRole, Intent
from src.services.chat.prompts import SYSTEM_GENERAL


class OllamaAnswerer(ChatAnswerPort):
    """Responde diretamente com o LLM, sem RAG nem internet."""

    intent = Intent.ASK_OLLAMA

    def __init__(
        self,
        llm: ConversationalLLMPort,
        *,
        max_history: int = 8,
    ) -> None:
        self._llm = llm
        self._max_history = max_history

    def answer(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        model = context.get("ollama_model")
        recent = history[-self._max_history :]
        messages = recent + [ChatMessage(role=ChatRole.USER, content=user_message)]
        text = self._llm.chat(messages, system_prompt=SYSTEM_GENERAL, model=model)
        return ChatAnswer(
            text=text,
            source=AnswerSource.OLLAMA,
            intent=self.intent,
        )
