"""Use case: conversar com o assistente jurídico (chatbot)."""

from __future__ import annotations

from src.domain.chat import ChatAnswer, ChatMessage
from src.services.chat.orchestrator import ChatOrchestrator


class ChatWithAssistantUseCase:
    """Ponto único de entrada para uma mensagem do chat."""

    def __init__(self, orchestrator: ChatOrchestrator) -> None:
        self._orchestrator = orchestrator

    def execute(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        return self._orchestrator.respond(user_message, history, context)
