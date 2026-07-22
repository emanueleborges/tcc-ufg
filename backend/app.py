"""Ponto de entrada da aplicação Crítico Jurídico Inteligente.

Modos de execução:

- ``streamlit run app.py``    → abre a interface web Streamlit
- ``python app.py``           → abre a interface web (lança o Streamlit)
- ``python app.py ui``        → idem
- ``python app.py api``       → sobe a API HTTP (frontend estilo ChatGPT)
- ``python app.py index``     → cria/atualiza o índice RAG
- ``python app.py scrape``    → baixa PDFs públicos para alimentar a base
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_on_path() -> None:
    """Garante que o pacote ``src`` é importável independentemente do CWD."""
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _is_streamlit_runtime() -> bool:
    """Detecta se este módulo está sendo executado dentro do Streamlit."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return False
    return get_script_run_ctx() is not None


_ensure_project_on_path()


if _is_streamlit_runtime():
    from src.presentation.streamlit.app import render

    render()
elif __name__ == "__main__":
    from src.presentation.cli.commands import run_cli

    raise SystemExit(run_cli(sys.argv[1:]))
