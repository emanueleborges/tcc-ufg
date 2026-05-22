"""LLM conversacional via LangChain + Ollama.

Encapsula ``langchain_ollama.ChatOllama`` por trás do port
``ConversationalLLMPort``, garantindo que o domínio fique livre da
dependência específica do LangChain.
"""

from __future__ import annotations

from functools import lru_cache

from src.application.ports import ConversationalLLMPort
from src.config.settings import OllamaSettings
from src.domain.chat import ChatMessage, ChatRole


@lru_cache(maxsize=8)
def _build_chat_model(host: str, model: str, temperature: float, num_ctx: int):
    """Cria uma instância única do ChatOllama por (host, modelo)."""
    from langchain_ollama import ChatOllama

    return ChatOllama(
        base_url=host,
        model=model,
        temperature=temperature,
        num_ctx=num_ctx,
    )


class LangChainOllamaChat(ConversationalLLMPort):
    """Adapter LangChain para o Ollama local."""

    def __init__(self, settings: OllamaSettings) -> None:
        self._settings = settings

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> str:
        chat_model = _build_chat_model(
            host=self._settings.host,
            model=model or self._settings.default_model,
            temperature=self._settings.temperature,
            num_ctx=self._settings.num_ctx,
        )
        lc_messages = _to_langchain_messages(messages, system_prompt)
        response = chat_model.invoke(lc_messages)
        return str(getattr(response, "content", response)).strip()


def _to_langchain_messages(messages: list[ChatMessage], system_prompt: str | None):
    """Converte o histórico de domínio em mensagens do LangChain."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    lc_messages = []
    if system_prompt:
        lc_messages.append(SystemMessage(content=system_prompt))
    for message in messages:
        if message.role is ChatRole.USER:
            lc_messages.append(HumanMessage(content=message.content))
        else:
            lc_messages.append(AIMessage(content=message.content))
    return lc_messages
