"""Dependências compartilhadas das rotas FastAPI."""

from __future__ import annotations

from functools import lru_cache

from src.container import AppContainer


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """Singleton do composition root (uma instância por processo)."""
    return AppContainer.default()
