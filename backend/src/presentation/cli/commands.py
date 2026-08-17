"""Comandos disponíveis na CLI da aplicação."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.container import AppContainer


def run_cli(argv: list[str] | None = None) -> int:
    """Roteia argumentos CLI para o comando correto."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "ui"

    container = AppContainer.default()

    if command == "ui":
        return _command_ui(container)
    if command == "api":
        return _command_api(args)
    if command == "index":
        return _command_index(container)
    if command == "scrape":
        return _command_scrape(container)

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description=(
            "Crítico Jurídico Inteligente (TCC UFG): RAG + análise de petições."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("ui", help="Inicia a interface web Streamlit (padrão)")
    api_parser = subparsers.add_parser(
        "api",
        help="Inicia a API HTTP FastAPI (para frontend estilo ChatGPT)",
    )
    api_parser.add_argument("--host", default="0.0.0.0", help="Host da API")
    api_parser.add_argument("--port", type=int, default=8000, help="Porta da API")
    api_parser.add_argument("--reload", action="store_true", help="Auto-reload em desenvolvimento")
    subparsers.add_parser("index", help="Cria/atualiza o índice RAG a partir dos PDFs aceitos")
    subparsers.add_parser("scrape", help="Baixa PDFs públicos para alimentar a base RAG")
    return parser


def _command_ui(container: AppContainer) -> int:
    entrypoint = Path(__file__).resolve().parents[3] / "app.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(entrypoint)])


def _command_api(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "src.presentation.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _command_index(container: AppContainer) -> int:
    chunks, documents, _embeddings = container.build_index_use_case.execute()
    report_path = container.generate_corpus_report_use_case.execute(documents, chunks)
    print(f"Índice RAG criado em: {container.settings.paths.index_dir}")
    print(f"Relatório do corpus:  {report_path}")
    print(f"Documentos: {len(documents)} | Chunks: {len(chunks)}")
    return 0


def _command_scrape(container: AppContainer) -> int:
    container.download_petitions_use_case.execute()
    return 0
