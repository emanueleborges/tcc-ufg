"""Visão de chat do Crítico Jurídico Inteligente.

O chatbot roteia a mensagem do usuário entre três fontes — RAG interno,
Ollama local e DuckDuckGo — e marca claramente a origem de cada resposta.
O upload de petições em PDF acontece dentro do próprio chat input, via
o recurso ``accept_file`` do Streamlit (1.40+).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.container import AppContainer
from src.domain.chat import (
    AnswerSource,
    ChatAnswer,
    ChatMessage,
    ChatRole,
    Citation,
    Intent,
)

_INTRO_MESSAGE = (
    "Olá! Sou seu assistente jurídico. **Roteio automaticamente** sua "
    "pergunta entre três fontes e mostro de onde veio a resposta:\n\n"
    "- 📚 **Base RAG** — quando você pergunta sobre temas jurídicos "
    "substantivos (dano moral, petições, jurisprudência, artigos de lei)\n"
    "- 🌐 **Internet (DuckDuckGo)** — quando há sinal temporal (anos, "
    "“atual”, “recente”, “notícias”) ou você pede explicitamente\n"
    "- 🤖 **Ollama local** — para conversa geral, dúvidas casuais ou "
    "quando nenhuma fonte específica se aplica\n\n"
    "Também aceito **upload de petição em PDF** direto no campo de "
    "mensagem (ícone de clipe). Anexe e peça _“analise”_ ⚖️ ou "
    "_“recrie esta petição”_ ✍️."
)

_SESSION_HISTORY_KEY = "chat_history"
_SESSION_PETITION_PATH_KEY = "chat_petition_path"
_SESSION_PETITION_NAME_KEY = "chat_petition_name"


def render(container: AppContainer) -> None:
    """Renderiza a visão de chat."""
    _ensure_session_state()

    st.title("💬 Crítico Jurídico Inteligente — chat")
    st.caption(
        "RAG · Ollama local · DuckDuckGo — cada resposta indica de onde veio."
    )

    chat_settings = _render_sidebar(container)
    _render_active_petition_banner()
    _render_history()
    _handle_user_input(container, chat_settings)


def _ensure_session_state() -> None:
    if _SESSION_HISTORY_KEY not in st.session_state:
        st.session_state[_SESSION_HISTORY_KEY] = [
            ChatMessage(
                role=ChatRole.ASSISTANT,
                content=_INTRO_MESSAGE,
                source=AnswerSource.SYSTEM,
            )
        ]
    st.session_state.setdefault(_SESSION_PETITION_PATH_KEY, None)
    st.session_state.setdefault(_SESSION_PETITION_NAME_KEY, None)


def _render_sidebar(container: AppContainer) -> dict:
    """Renderiza a barra lateral e devolve as configurações do chat."""
    settings = container.settings
    with st.sidebar:
        st.header("Configurações do chat")
        ollama_model = st.text_input(
            "Modelo Ollama",
            value=settings.ollama.default_model,
            help="Modelo local usado para todas as respostas (RAG, Ollama, Internet).",
        )
        rag_top_k = st.slider(
            "Trechos do RAG por resposta",
            min_value=2,
            max_value=12,
            value=settings.rag.top_k_similares,
        )
        web_max_results = st.slider(
            "Resultados da internet por resposta",
            min_value=2,
            max_value=10,
            value=settings.web_search.max_results,
        )
        use_internet_for_recreation = st.checkbox(
            "Usar internet ao recriar petição",
            value=True,
            help="Quando habilitado, a recriação consulta a internet por referências.",
        )

        st.divider()
        st.subheader("Base RAG")
        if st.button("Recriar índice RAG", use_container_width=True):
            _rebuild_index(container)
        if st.button("Baixar PDFs públicos", use_container_width=True):
            _run_scraping(container)

        st.divider()
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state[_SESSION_HISTORY_KEY] = []
            st.session_state[_SESSION_PETITION_PATH_KEY] = None
            st.session_state[_SESSION_PETITION_NAME_KEY] = None
            _ensure_session_state()
            st.rerun()

    return {
        "ollama_model": ollama_model.strip() or settings.ollama.default_model,
        "rag_top_k": rag_top_k,
        "web_max_results": web_max_results,
        "use_internet": use_internet_for_recreation,
    }


def _render_active_petition_banner() -> None:
    """Mostra qual petição está anexada e oferece botão para remover."""
    name = st.session_state.get(_SESSION_PETITION_NAME_KEY)
    if not name:
        return
    col_info, col_action = st.columns([4, 1])
    with col_info:
        st.info(
            f"📎 Petição anexada: **{name}** — peça _“analise”_ ou _“recrie”_ "
            "para acionar a avaliação."
        )
    with col_action:
        if st.button("Remover", use_container_width=True, key="remove_petition_btn"):
            st.session_state[_SESSION_PETITION_PATH_KEY] = None
            st.session_state[_SESSION_PETITION_NAME_KEY] = None
            st.rerun()


def _persist_upload(container: AppContainer, uploaded_file) -> Path:
    uploads_dir = container.settings.paths.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    petition_path = uploads_dir / uploaded_file.name
    petition_path.write_bytes(uploaded_file.getbuffer())
    return petition_path


def _run_scraping(container: AppContainer) -> None:
    with st.spinner("Baixando PDFs públicos..."):
        try:
            result = container.download_petitions_use_case.execute()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao baixar PDFs: {exc}")
            return
    st.success(result.message)


def _rebuild_index(container: AppContainer) -> None:
    with st.spinner("Recriando índice RAG..."):
        try:
            chunks, documents, _ = container.build_index_use_case.execute()
            report = container.generate_corpus_report_use_case.execute(documents, chunks)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao recriar índice: {exc}")
            return
    st.success(f"Índice atualizado. Relatório: {report}")


def _render_history() -> None:
    history: list[ChatMessage] = st.session_state[_SESSION_HISTORY_KEY]
    for message in history:
        avatar = _avatar_for_role(message.role, message.source)
        with st.chat_message(message.role.value, avatar=avatar):
            if message.role is ChatRole.ASSISTANT and message.source is not None:
                _render_source_badge(message.source, message.routing_mode, message.model)
            st.markdown(message.content)
            if message.citations:
                _render_citations(message.citations, message.source)
            if message.routing_reason:
                st.caption(f"Roteamento: _{message.routing_reason}_")


def _avatar_for_role(role: ChatRole, source: AnswerSource | None) -> str:
    if role is ChatRole.USER:
        return "🧑"
    if source is None:
        return "🤖"
    return source.icon


def _render_source_badge(
    source: AnswerSource,
    routing_mode: str | None = None,
    model: str | None = None,
) -> None:
    """Renderiza a fonte + modelo + modo de roteamento da resposta."""
    color_map = {
        AnswerSource.RAG: "blue",
        AnswerSource.OLLAMA: "violet",
        AnswerSource.INTERNET: "green",
        AnswerSource.PETITION_ANALYSIS: "orange",
        AnswerSource.PETITION_RECREATION: "red",
        AnswerSource.SYSTEM: "gray",
    }
    color = color_map.get(source, "gray")
    parts: list[str] = [f"{source.icon} **Fonte:** {source.label}"]
    if model and source in _SOURCES_USING_LLM:
        parts.append(f"· **Modelo:** `{model}`")
    if routing_mode:
        parts.append(f"· **Roteamento:** {routing_mode}")
    st.markdown(f":{color}-background[{' '.join(parts)}]")


_SOURCES_USING_LLM = {
    AnswerSource.RAG,
    AnswerSource.OLLAMA,
    AnswerSource.INTERNET,
    AnswerSource.PETITION_RECREATION,
}


def _render_citations(citations: list[Citation], source: AnswerSource | None) -> None:
    if not citations:
        return
    label = "Referências" if source is AnswerSource.INTERNET else "Trechos usados"
    with st.expander(f"{label} ({len(citations)})"):
        for index, citation in enumerate(citations, start=1):
            header = (
                f"**{index}. [{citation.title}]({citation.url})**"
                if citation.url
                else f"**{index}. {citation.title}**"
            )
            st.markdown(header)
            if citation.detail:
                st.caption(citation.detail)


def _handle_user_input(container: AppContainer, chat_settings: dict) -> None:
    placeholder = (
        "Pergunte algo ou anexe uma petição em PDF…  "
        "ex.: 'analise minha petição', 'compare com a base RAG', "
        "'pesquise na internet sobre dano moral coletivo'"
    )
    submitted = st.chat_input(
        placeholder,
        accept_file=True,
        file_type=["pdf"],
    )
    if not submitted:
        return

    user_text, attached_files = _split_chat_input(submitted)
    petition_name = _process_attachments(container, attached_files)

    if not user_text and petition_name:
        user_text = f"_Anexei a petição **{petition_name}**._"

    if not user_text:
        return

    history: list[ChatMessage] = st.session_state[_SESSION_HISTORY_KEY]
    history.append(ChatMessage(role=ChatRole.USER, content=user_text))

    with st.chat_message(ChatRole.USER.value, avatar="🧑"):
        if petition_name:
            st.caption(f"📎 Anexado: {petition_name}")
        st.markdown(user_text)

    with st.chat_message(ChatRole.ASSISTANT.value, avatar="🤖"):
        with st.spinner("Pensando..."):
            answer = _run_assistant(container, history, chat_settings, user_text)
        routing_mode = answer.extra.get("classification_mode_label")
        routing_reason = answer.extra.get("classification_reason")
        model_used = chat_settings.get("ollama_model")
        _render_source_badge(answer.source, routing_mode, model_used)
        st.markdown(answer.text)
        if answer.citations:
            _render_citations(answer.citations, answer.source)
        if routing_reason:
            st.caption(f"Roteamento: _{routing_reason}_")

    history.append(
        ChatMessage(
            role=ChatRole.ASSISTANT,
            content=answer.text,
            source=answer.source,
            citations=answer.citations,
            routing_mode=routing_mode,
            routing_reason=routing_reason,
            model=model_used,
        )
    )


def _split_chat_input(submitted) -> tuple[str, list]:
    """Compatível com ambos os formatos retornados por ``st.chat_input``.

    - Quando ``accept_file`` está ativo: retorna um objeto com ``.text`` e ``.files``.
    - Quando o usuário só digita texto puro: pode vir uma string.
    """
    if isinstance(submitted, str):
        return submitted.strip(), []
    text = (getattr(submitted, "text", None) or "").strip()
    files = list(getattr(submitted, "files", []) or [])
    return text, files


def _process_attachments(container: AppContainer, files: list) -> str | None:
    """Persiste o primeiro PDF anexado e devolve o nome dele (se houver)."""
    if not files:
        return None
    pdf_files = [f for f in files if str(getattr(f, "name", "")).lower().endswith(".pdf")]
    if not pdf_files:
        st.warning("Apenas arquivos PDF são aceitos como petição. Anexo ignorado.")
        return None
    petition_file = pdf_files[0]
    petition_path = _persist_upload(container, petition_file)
    st.session_state[_SESSION_PETITION_PATH_KEY] = str(petition_path)
    st.session_state[_SESSION_PETITION_NAME_KEY] = petition_file.name
    return petition_file.name


def _run_assistant(
    container: AppContainer,
    history: list[ChatMessage],
    chat_settings: dict,
    user_message: str,
) -> ChatAnswer:
    context = {
        "ollama_model": chat_settings["ollama_model"],
        "rag_top_k": chat_settings["rag_top_k"],
        "web_max_results": chat_settings["web_max_results"],
        "use_internet": chat_settings["use_internet"],
        "petition_path": st.session_state.get(_SESSION_PETITION_PATH_KEY),
    }
    history_without_last = history[:-1]
    try:
        return container.chat_with_assistant_use_case.execute(
            user_message=user_message,
            history=history_without_last,
            context=context,
        )
    except Exception as exc:  # noqa: BLE001
        return ChatAnswer(
            text=f"Falha inesperada no assistente: {exc}",
            source=AnswerSource.SYSTEM,
            intent=Intent.ASK_OLLAMA,
        )
