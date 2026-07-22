"""Rotas HTTP da API — contrato para frontend estilo ChatGPT."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.container import AppContainer
from src.domain.chat import ChatMessage, ChatRole
from src.presentation.api.deps import get_container
from src.presentation.api.schemas import (
    AnalysisOut,
    ChatChoiceOut,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageOut,
    CitationOut,
    HealthResponse,
    IndexRebuildResponse,
    IndexStatusResponse,
    ModelOut,
    ModelsListResponse,
    RecreationOut,
    RoutingOut,
    ScrapeResponse,
    SourceOut,
    UploadResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health & discovery
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Healthcheck simples para o frontend/proxy."""
    return HealthResponse()


@router.get("/v1/models", response_model=ModelsListResponse, tags=["chat"])
def list_models(container: AppContainer = Depends(get_container)) -> ModelsListResponse:
    """Lista modelos/fontes disponíveis (formato próximo ao OpenAI)."""
    default_model = container.settings.ollama.default_model
    return ModelsListResponse(
        data=[
            ModelOut(
                id=default_model,
                owned_by="ollama",
                description="LLM local (Ollama) usado em chat, RAG e internet.",
            ),
            ModelOut(
                id="rag",
                owned_by="critico-juridico",
                description="Base RAG jurídica interna (roteamento automático).",
            ),
            ModelOut(
                id="internet",
                owned_by="duckduckgo",
                description="Busca web via DuckDuckGo (roteamento automático).",
            ),
            ModelOut(
                id="petition-analysis",
                owned_by="critico-juridico",
                description="Análise crítica de petição anexada.",
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Chat (estilo ChatGPT / OpenAI Completions)
# ---------------------------------------------------------------------------


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    tags=["chat"],
    summary="Envia mensagem ao assistente (estilo ChatGPT)",
)
def chat_completions(
    body: ChatCompletionRequest,
    container: AppContainer = Depends(get_container),
) -> ChatCompletionResponse:
    """
    Endpoint principal do chatbot.

    Aceita histórico no formato OpenAI (`messages`) e responde com
    `choices[0].message.content`, além de metadados de fonte/roteamento.
    """
    user_message, history = _split_messages(body.messages)
    if not user_message:
        raise HTTPException(status_code=400, detail="A última mensagem precisa ser do usuário.")

    petition_path = _resolve_petition_path(container, body.petition_id)
    context = {
        "ollama_model": body.model,
        "rag_top_k": body.rag_top_k,
        "web_max_results": body.web_max_results,
        "use_internet": body.use_internet_on_recreate,
        "petition_path": petition_path,
    }

    try:
        answer = container.chat_with_assistant_use_case.execute(
            user_message=user_message,
            history=history,
            context=context,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha no assistente: {exc}") from exc

    analysis = _extract_analysis(answer.extra)
    recreation = _extract_recreation(answer.extra)

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=body.model,
        choices=[
            ChatChoiceOut(
                message=ChatMessageOut(role="assistant", content=answer.text),
            )
        ],
        source=SourceOut(
            id=answer.source.value,
            label=answer.source.label,
            icon=answer.source.icon,
        ),
        routing=RoutingOut(
            intent=answer.intent.value,
            mode=str(answer.extra.get("classification_mode", "default")),
            reason=str(answer.extra.get("classification_reason", "")),
        ),
        citations=[
            CitationOut(title=c.title, detail=c.detail, url=c.url)
            for c in answer.citations
        ],
        analysis=analysis,
        recreation=recreation,
        extra={
            k: v
            for k, v in answer.extra.items()
            if k not in {"review", "recreated"} and _is_json_safe(v)
        },
    )


def _extract_analysis(extra: dict) -> AnalysisOut | None:
    review = extra.get("review")
    if review is None:
        return None
    return AnalysisOut(
        scores=dict(getattr(review, "scores", {}) or {}),
        problems=list(getattr(review, "problems", []) or []),
        suggestions=list(getattr(review, "suggestions", []) or []),
        features=dict(getattr(review, "features", {}) or {}),
        markdown=str(getattr(review, "markdown", "") or ""),
    )


def _extract_recreation(extra: dict) -> RecreationOut | None:
    recreated = extra.get("recreated")
    if recreated is None:
        return None
    return RecreationOut(
        markdown=str(getattr(recreated, "markdown", "") or ""),
        warnings=list(getattr(recreated, "warnings", []) or []),
        used_ollama=bool(getattr(recreated, "used_ollama", False)),
    )


def _split_messages(messages: list) -> tuple[str, list[ChatMessage]]:
    """Separa a última mensagem do usuário do histórico anterior."""
    history: list[ChatMessage] = []
    user_message = ""

    for index, msg in enumerate(messages):
        is_last = index == len(messages) - 1
        if msg.role == "user" and is_last:
            user_message = msg.content.strip()
            continue
        if msg.role == "system":
            continue
        role = ChatRole.USER if msg.role == "user" else ChatRole.ASSISTANT
        history.append(ChatMessage(role=role, content=msg.content))

    return user_message, history


def _resolve_petition_path(container: AppContainer, petition_id: str | None) -> str | None:
    if not petition_id:
        return None
    uploads_dir = container.settings.paths.uploads_dir
    matches = list(uploads_dir.glob(f"{petition_id}_*"))
    if not matches:
        # aceita também o nome bruto do arquivo
        candidate = uploads_dir / petition_id
        if candidate.exists():
            return str(candidate)
        raise HTTPException(
            status_code=404,
            detail=f"Petição '{petition_id}' não encontrada. Faça upload em POST /v1/uploads.",
        )
    return str(matches[0])


def _is_json_safe(value: object) -> bool:
    return isinstance(value, (str, int, float, bool, type(None), list, dict))


# ---------------------------------------------------------------------------
# Uploads (petição em PDF)
# ---------------------------------------------------------------------------


@router.post(
    "/v1/uploads",
    response_model=UploadResponse,
    tags=["uploads"],
    summary="Faz upload de petição em PDF",
)
async def upload_petition(
    file: UploadFile = File(..., description="Petição em PDF"),
    container: AppContainer = Depends(get_container),
) -> UploadResponse:
    """Salva o PDF e devolve ``petition_id`` para usar em ``/v1/chat/completions``."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    petition_id = uuid.uuid4().hex[:12]
    safe_name = Path(file.filename).name
    uploads_dir = container.settings.paths.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / f"{petition_id}_{safe_name}"
    target.write_bytes(data)

    return UploadResponse(
        petition_id=petition_id,
        file_name=safe_name,
        path=str(target),
        size_bytes=len(data),
        uploaded_at=datetime.now(timezone.utc),
    )


@router.get(
    "/v1/uploads/{petition_id}",
    response_model=UploadResponse,
    tags=["uploads"],
)
def get_upload(
    petition_id: str,
    container: AppContainer = Depends(get_container),
) -> UploadResponse:
    """Retorna metadados de uma petição já enviada."""
    path_str = _resolve_petition_path(container, petition_id)
    if not path_str:
        raise HTTPException(status_code=404, detail="Petição não encontrada.")
    path = Path(path_str)
    return UploadResponse(
        petition_id=petition_id,
        file_name=path.name.split("_", 1)[-1] if "_" in path.name else path.name,
        path=str(path),
        size_bytes=path.stat().st_size,
        uploaded_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# RAG index & scraping
# ---------------------------------------------------------------------------


@router.get("/v1/index", response_model=IndexStatusResponse, tags=["rag"])
def index_status(container: AppContainer = Depends(get_container)) -> IndexStatusResponse:
    """Status do índice RAG em disco."""
    repo = container.index_repository
    if not repo.exists():
        return IndexStatusResponse(
            exists=False,
            index_dir=str(container.settings.paths.index_dir),
        )
    try:
        chunks, documents, _ = repo.load()
        return IndexStatusResponse(
            exists=True,
            index_dir=str(container.settings.paths.index_dir),
            documents=len(documents),
            chunks=len(chunks),
        )
    except Exception:  # noqa: BLE001
        return IndexStatusResponse(
            exists=True,
            index_dir=str(container.settings.paths.index_dir),
        )


@router.post(
    "/v1/index/rebuild",
    response_model=IndexRebuildResponse,
    tags=["rag"],
    summary="Recria o índice RAG a partir dos PDFs aceitos",
)
def rebuild_index(container: AppContainer = Depends(get_container)) -> IndexRebuildResponse:
    try:
        chunks, documents, _ = container.build_index_use_case.execute()
        report = container.generate_corpus_report_use_case.execute(documents, chunks)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IndexRebuildResponse(
        documents=len(documents),
        chunks=len(chunks),
        report_path=str(report),
        index_dir=str(container.settings.paths.index_dir),
    )


@router.post(
    "/v1/index/rebuild/stream",
    tags=["rag"],
    summary="Recria o índice RAG com progresso (NDJSON)",
)
def rebuild_index_stream(
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_job(_run_rebuild_job, container),
        media_type="application/x-ndjson",
    )


@router.post(
    "/v1/scrape",
    response_model=ScrapeResponse,
    tags=["rag"],
    summary="Baixa PDFs públicos para a base RAG",
)
def scrape_petitions(container: AppContainer = Depends(get_container)) -> ScrapeResponse:
    try:
        total = container.download_petitions_use_case.execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ScrapeResponse(
        total_documents=total,
        message="Scraping concluído. Revise os PDFs e rode POST /v1/index/rebuild.",
    )


@router.post(
    "/v1/scrape/stream",
    tags=["rag"],
    summary="Baixa PDFs públicos com progresso (NDJSON)",
)
def scrape_petitions_stream(
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_job(_run_scrape_job, container),
        media_type="application/x-ndjson",
    )


def _run_rebuild_job(
    container: AppContainer,
    on_progress: Callable[[int, str], None],
) -> dict:
    chunks, documents, _ = container.build_index_use_case.execute(on_progress=on_progress)
    report = container.generate_corpus_report_use_case.execute(documents, chunks)
    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "report_path": str(report),
        "index_dir": str(container.settings.paths.index_dir),
    }


def _run_scrape_job(
    container: AppContainer,
    on_progress: Callable[[int, str], None],
) -> dict:
    total = container.download_petitions_use_case.execute(on_progress=on_progress)
    return {
        "total_documents": total,
        "message": "Scraping concluído. Revise os PDFs e rode POST /v1/index/rebuild.",
    }


def _stream_job(job_fn, container: AppContainer) -> Iterator[str]:
    """Executa um job em thread e emite eventos NDJSON de progresso/resultado."""
    events: Queue = Queue()

    def on_progress(percent: int, message: str) -> None:
        events.put({"type": "progress", "percent": percent, "message": message})

    def worker() -> None:
        try:
            result = job_fn(container, on_progress)
            events.put({"type": "done", "result": result})
        except Exception as exc:  # noqa: BLE001
            events.put({"type": "error", "detail": str(exc)})
        finally:
            events.put(None)

    Thread(target=worker, daemon=True).start()
    while True:
        try:
            item = events.get(timeout=0.5)
        except Empty:
            # keep-alive para proxies/browser
            yield json.dumps({"type": "ping"}) + "\n"
            continue
        if item is None:
            break
        yield json.dumps(item, ensure_ascii=False) + "\n"
