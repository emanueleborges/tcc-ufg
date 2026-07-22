"""Factory da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.api.routes import router


def create_app() -> FastAPI:
    """Cria e configura a API HTTP do Crítico Jurídico."""
    app = FastAPI(
        title="Crítico Jurídico Inteligente API",
        description=(
            "Backend HTTP para frontend estilo ChatGPT.\n\n"
            "Endpoint principal: `POST /v1/chat/completions` "
            "(formato próximo ao OpenAI Chat Completions).\n\n"
            "Upload de petição: `POST /v1/uploads` → use o `petition_id` no chat."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


# Instância ASGI usada por `uvicorn src.presentation.api.app:app`
app = create_app()
