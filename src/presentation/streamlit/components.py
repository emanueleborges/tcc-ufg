"""Componentes Streamlit reutilizáveis (visualizadores, blocos prontos)."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


def render_pdf_viewer(pdf_path: Path, *, height: int = 900) -> None:
    """Embute um visualizador de PDF inline na página Streamlit."""
    pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <iframe
            src="data:application/pdf;base64,{pdf_base64}"
            width="100%"
            height="{height}"
            style="border: 1px solid #ddd; border-radius: 8px;"
            type="application/pdf">
        </iframe>
        """,
        unsafe_allow_html=True,
    )
