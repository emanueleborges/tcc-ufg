"""Estratégia de resposta direta via Ollama (chat geral)."""

from __future__ import annotations

from src.application.ports import ChatAnswerPort, ConversationalLLMPort
from src.domain.chat import AnswerSource, ChatAnswer, ChatMessage, ChatRole, Intent
from src.services.chat.legal_anchors import find_legal_anchor, is_tiny_model
from src.services.chat.personas import DEFAULT_PERSONA_ID, get_persona
from src.services.chat.prompts import (
    SYSTEM_GENERAL,
    resolve_persona_id,
    resolve_system_prompt,
    resolve_user_message,
)


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
        persona_id = resolve_persona_id(context)
        persona = get_persona(persona_id)
        anchor = find_legal_anchor(user_message, persona.id)

        # Modelos 1b–3b alucinam institutos clássicos mesmo com system prompt forte.
        if anchor and is_tiny_model(str(model) if model else None):
            return ChatAnswer(
                text=anchor.direct_answer,
                source=AnswerSource.OLLAMA,
                intent=self.intent,
                extra={
                    "persona_id": persona.id,
                    "persona_label": persona.label,
                    "legal_anchor_id": anchor.id,
                    "grounded_direct": True,
                },
            )

        steered = resolve_user_message(user_message, context)

        # Personas especializadas: não reaproveitar respostas anteriores do assistente
        # (modelos pequenos costumam copiar o erro do histórico).
        if persona.id != DEFAULT_PERSONA_ID:
            recent_users = [
                message
                for message in history
                if message.role is ChatRole.USER
            ][-2:]
            messages = recent_users + [
                ChatMessage(role=ChatRole.USER, content=steered)
            ]
        else:
            recent = history[-self._max_history :]
            messages = recent + [ChatMessage(role=ChatRole.USER, content=steered)]

        text = self._llm.chat(
            messages,
            system_prompt=resolve_system_prompt(SYSTEM_GENERAL, context),
            model=model,
        )
        return ChatAnswer(
            text=text,
            source=AnswerSource.OLLAMA,
            intent=self.intent,
            extra={
                "persona_id": persona.id,
                "persona_label": persona.label,
                **({"legal_anchor_id": anchor.id} if anchor else {}),
            },
        )
