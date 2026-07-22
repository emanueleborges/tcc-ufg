"""Entrypoint do Streamlit: alterna entre o chatbot e a visão clássica."""

from __future__ import annotations

import streamlit as st

from src.container import AppContainer
from src.presentation.streamlit import chat_view, classic_view

_PAGE_CHAT = "Chat"
_PAGE_CLASSIC = "Análise clássica"
_SESSION_PAGE_KEY = "selected_page"


def render() -> None:
    """Roteador da interface web."""
    _configure_page()
    container = AppContainer.default()

    selected = _render_page_selector()

    if selected == _PAGE_CLASSIC:
        classic_view.render(container)
    else:
        chat_view.render(container)


def _configure_page() -> None:
    st.set_page_config(
        page_title="Crítico Jurídico IA",
        page_icon="⚖️",
        layout="wide",
    )


def _render_page_selector() -> str:
    """Mostra o seletor de modo no topo da sidebar e retorna o escolhido."""
    with st.sidebar:
        st.markdown("### Modo de uso")
        selected = st.radio(
            label="Modo",
            options=[_PAGE_CHAT, _PAGE_CLASSIC],
            index=0,
            key=_SESSION_PAGE_KEY,
            label_visibility="collapsed",
        )
        st.divider()
    return selected
