"""Orquestrador do chatbot: classifica intenção e delega à estratégia."""

from __future__ import annotations

from src.application.ports import ChatAnswerPort
from src.domain.chat import ChatAnswer, ChatMessage, Intent
from src.services.chat.intent_classifier import classify_intent


class ChatOrchestrator:
    """Recebe a mensagem do usuário e produz a resposta correspondente."""

    def __init__(self, strategies: dict[Intent, ChatAnswerPort]) -> None:
        missing = [intent for intent in Intent if intent not in strategies]
        if missing:
            raise ValueError(
                "ChatOrchestrator precisa de estratégias para todas as intenções. "
                f"Faltam: {[m.value for m in missing]}"
            )
        self._strategies = strategies

    def respond(
        self,
        user_message: str,
        history: list[ChatMessage],
        context: dict,
    ) -> ChatAnswer:
        has_petition = bool(context.get("petition_path"))
        classified = classify_intent(user_message, has_petition=has_petition)
        strategy = self._strategies[classified.intent]
        answer = strategy.answer(user_message, history, context)
        extra = dict(answer.extra)
        extra.setdefault("classification_reason", classified.reason)
        extra.setdefault("classification_mode", classified.mode.value)
        extra.setdefault("classification_mode_label", classified.mode.label)
        return ChatAnswer(
            text=answer.text,
            source=answer.source,
            intent=answer.intent,
            citations=answer.citations,
            extra=extra,
        )
