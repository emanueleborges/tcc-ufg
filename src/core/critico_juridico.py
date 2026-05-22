#!/usr/bin/env python3
"""Compatibilidade: gera o índice RAG usando o script separado rag_index.py."""

from rag_index import main


if __name__ == "__main__":
    raise SystemExit(main())
