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
from src.application.use_cases.analysis_times import format_seconds
from src.application.use_cases.reading_times import format_minutes
from src.domain.chat import ChatMessage, ChatRole
from src.domain.validation import (
    HumanValidation,
    HumanValidationInput,
    ProblemAssessment,
    ReadingTimeEntry,
)
from src.presentation.api.deps import get_container
from src.presentation.api.schemas import (
    AnalysisOut,
    ChatChoiceOut,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageOut,
    CitationOut,
    ComparisonOut,
    HealthResponse,
    HumanValidationCreateRequest,
    HumanValidationListResponse,
    HumanValidationOut,
    IndexRebuildResponse,
    IndexStatusResponse,
    ModelOut,
    ModelsListResponse,
    PersonaOut,
    PersonasListResponse,
    ProblemAssessmentOut,
    PromptInjectionFindingOut,
    PromptInjectionOut,
    RoutingOut,
    ScrapeResponse,
    AnalysisTimeListResponse,
    AnalysisTimeOut,
    AnalysisTimeSummaryOut,
    MeasureAnalysisTimeRequest,
    MeasureAnalysisTimeResponse,
    ReadingTimeCreateRequest,
    ReadingTimeListResponse,
    ReadingTimeOut,
    ReadingTimeSummaryOut,
    ReadingTimeUpdateRequest,
    SourceOut,
    UploadResponse,
    ValidationMetricsResponse,
    ValidationSummaryOut,
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
    ollama_models = _list_ollama_model_ids(container.settings.ollama.host)
    if default_model not in ollama_models:
        ollama_models.insert(0, default_model)
    else:
        ollama_models = [default_model] + [m for m in ollama_models if m != default_model]

    data = [
        ModelOut(
            id=model_id,
            owned_by="ollama",
            description="LLM local (Ollama) usado em chat, RAG e internet.",
        )
        for model_id in ollama_models
    ]
    data.extend(
        [
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
    return ModelsListResponse(data=data)


def _list_ollama_model_ids(host: str) -> list[str]:
    """Consulta `/api/tags` do Ollama; em falha devolve lista vazia."""
    import urllib.error
    import urllib.request

    base = host.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    models = payload.get("models") or []
    names: list[str] = []
    for item in models:
        name = str(item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


@router.get("/v1/personas", response_model=PersonasListResponse, tags=["chat"])
def list_personas() -> PersonasListResponse:
    """Lista personas jurídicas disponíveis para o chat."""
    from src.services.chat.personas import DEFAULT_PERSONA_ID, list_personas as _list

    return PersonasListResponse(
        default_id=DEFAULT_PERSONA_ID,
        data=[
            PersonaOut(id=item.id, label=item.label, description=item.description)
            for item in _list()
        ],
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
        "petition_path": petition_path,
        "persona_id": body.persona_id,
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
    persona = _resolve_persona_out(body.persona_id, answer.extra)

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
        persona=persona,
        citations=[
            CitationOut(title=c.title, detail=c.detail, url=c.url)
            for c in answer.citations
        ],
        analysis=analysis,
        extra={
            k: v
            for k, v in answer.extra.items()
            if k != "review" and _is_json_safe(v)
        },
    )


def _resolve_persona_out(persona_id: str, extra: dict) -> PersonaOut:
    from src.services.chat.personas import get_persona

    persona = get_persona(str(extra.get("persona_id") or persona_id))
    return PersonaOut(
        id=persona.id,
        label=str(extra.get("persona_label") or persona.label),
        description=persona.description,
    )


def _extract_analysis(extra: dict) -> AnalysisOut | None:
    review = extra.get("review")
    if review is None:
        return None
    injection = getattr(review, "prompt_injection", None)
    prompt_injection = None
    if injection is not None:
        prompt_injection = PromptInjectionOut(
            risk=str(getattr(injection, "risk", "none") or "none"),  # type: ignore[arg-type]
            score=int(getattr(injection, "score", 0) or 0),
            summary=str(getattr(injection, "summary", "") or ""),
            findings=[
                PromptInjectionFindingOut(
                    pattern_id=str(getattr(item, "pattern_id", "")),
                    severity=str(getattr(item, "severity", "")),
                    description=str(getattr(item, "description", "")),
                    excerpt=str(getattr(item, "excerpt", "")),
                    matched=str(getattr(item, "matched", "")),
                    owasp_categories=list(getattr(item, "owasp_categories", ()) or ()),
                )
                for item in list(getattr(injection, "findings", []) or [])
            ],
            scanned_chars=int(getattr(injection, "scanned_chars", 0) or 0),
            owasp_id=str(getattr(injection, "owasp_id", "LLM01:2025") or "LLM01:2025"),
            owasp_name=str(getattr(injection, "owasp_name", "Prompt Injection") or "Prompt Injection"),
            owasp_url=str(
                getattr(
                    injection,
                    "owasp_url",
                    "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
                )
                or "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"
            ),
            attack_types=list(getattr(injection, "attack_types", ()) or ()),
            techniques=list(getattr(injection, "techniques", ()) or ()),
            objectives=list(getattr(injection, "objectives", ()) or ()),
            verdict=str(getattr(injection, "verdict", "clean") or "clean"),  # type: ignore[arg-type]
        )
    return AnalysisOut(
        scores=dict(getattr(review, "scores", {}) or {}),
        problems=list(getattr(review, "problems", []) or []),
        suggestions=list(getattr(review, "suggestions", []) or []),
        features=dict(getattr(review, "features", {}) or {}),
        markdown=str(getattr(review, "markdown", "") or ""),
        prompt_injection=prompt_injection,
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
        result = container.download_petitions_use_case.execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ScrapeResponse(
        total_documents=result.total_documents,
        message=result.message,
        new_accepted=result.new_accepted,
        new_rejected=result.new_rejected,
        new_partial=result.new_partial,
        candidates_found=result.candidates_found,
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


# ---------------------------------------------------------------------------
# Validação humana (lawyer-in-the-loop)
# ---------------------------------------------------------------------------


@router.post(
    "/v1/validations",
    response_model=HumanValidationOut,
    tags=["validation"],
    summary="Registra validação humana e compara com o protótipo",
)
def create_human_validation(
    body: HumanValidationCreateRequest,
    container: AppContainer = Depends(get_container),
) -> HumanValidationOut:
    try:
        validation = container.submit_human_validation_use_case.execute(
            HumanValidationInput(
                petition_id=body.petition_id,
                petition_name=body.petition_name,
                reviewer_name=body.reviewer_name,
                prototype_scores=body.prototype_scores,
                human_scores=body.human_scores,
                problem_assessments=[
                    ProblemAssessment(
                        problem=item.problem,
                        verdict=item.verdict,
                        note=item.note,
                    )
                    for item in body.problem_assessments
                ],
                documentation_ok=body.documentation_ok,
                textual_cohesion_ok=body.textual_cohesion_ok,
                argumentative_consistency_ok=body.argumentative_consistency_ok,
                legal_basis_ok=body.legal_basis_ok,
                final_quality=body.final_quality,
                comments=body.comments,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _validation_to_out(validation)


@router.get(
    "/v1/validations",
    response_model=HumanValidationListResponse,
    tags=["validation"],
    summary="Lista validações e resumo de aderência humano × protótipo",
)
def list_human_validations(
    container: AppContainer = Depends(get_container),
) -> HumanValidationListResponse:
    items, summary = container.list_human_validations_use_case.execute()
    return HumanValidationListResponse(
        items=[_validation_to_out(item) for item in items],
        summary=ValidationSummaryOut(**summary),
    )


@router.get(
    "/v1/validations/metrics",
    response_model=ValidationMetricsResponse,
    tags=["validation"],
    summary="Métricas agregadas das validações humanas (dashboard do TCC)",
)
def validation_metrics(
    container: AppContainer = Depends(get_container),
) -> ValidationMetricsResponse:
    return ValidationMetricsResponse(
        **container.get_validation_metrics_use_case.execute()
    )


# ---------------------------------------------------------------------------
# Tempos de leitura humana (registro simples: advogado + tempo)
# ---------------------------------------------------------------------------


@router.post(
    "/v1/reading-times",
    response_model=ReadingTimeOut,
    tags=["reading-times"],
    summary="Registra o tempo que um advogado gastou lendo uma petição",
)
def create_reading_time(
    body: ReadingTimeCreateRequest,
    container: AppContainer = Depends(get_container),
) -> ReadingTimeOut:
    try:
        entry = container.submit_reading_time_use_case.execute(
            lawyer_name=body.lawyer_name,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _reading_time_to_out(entry)


@router.get(
    "/v1/reading-times",
    response_model=ReadingTimeListResponse,
    tags=["reading-times"],
    summary="Lista tempos de leitura humanos e a média",
)
def list_reading_times(
    container: AppContainer = Depends(get_container),
) -> ReadingTimeListResponse:
    items, summary = container.list_reading_times_use_case.execute()
    return ReadingTimeListResponse(
        items=[_reading_time_to_out(item) for item in items],
        summary=ReadingTimeSummaryOut(**summary),
    )


@router.put(
    "/v1/reading-times/{entry_id}",
    response_model=ReadingTimeOut,
    tags=["reading-times"],
    summary="Atualiza um registro de tempo de leitura",
)
def update_reading_time(
    entry_id: str,
    body: ReadingTimeUpdateRequest,
    container: AppContainer = Depends(get_container),
) -> ReadingTimeOut:
    try:
        updated = container.update_reading_time_use_case.execute(
            entry_id=entry_id,
            lawyer_name=body.lawyer_name,
            minutes=body.minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    entry = container.reading_time_repository.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    return _reading_time_to_out(entry)


@router.delete(
    "/v1/reading-times/{entry_id}",
    status_code=204,
    tags=["reading-times"],
    summary="Remove um registro de tempo de leitura",
)
def delete_reading_time(
    entry_id: str,
    container: AppContainer = Depends(get_container),
) -> None:
    deleted = container.delete_reading_time_use_case.execute(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")




@router.get(
    "/v1/analysis-times",
    response_model=AnalysisTimeListResponse,
    tags=["analysis-times"],
    summary="Lista medições reais de tempo da análise pela aplicação",
)
def list_analysis_times(
    container: AppContainer = Depends(get_container),
) -> AnalysisTimeListResponse:
    items, summary = container.list_analysis_times_use_case.execute()
    return AnalysisTimeListResponse(
        items=[_analysis_time_to_out(item) for item in items],
        summary=AnalysisTimeSummaryOut(**summary),
    )


@router.post(
    "/v1/analysis-times/measure",
    response_model=MeasureAnalysisTimeResponse,
    tags=["analysis-times"],
    summary="Mede o tempo real da análise (N execuções) e atualiza a média",
)
def measure_analysis_times(
    body: MeasureAnalysisTimeRequest | None = None,
    container: AppContainer = Depends(get_container),
) -> MeasureAnalysisTimeResponse:
    body = body or MeasureAnalysisTimeRequest()
    chunks, documents, embeddings = container.load_or_build_index_use_case.execute()
    petition_path = None
    if body.petition_id:
        from pathlib import Path
        uploads = container.settings.paths.uploads_dir
        matches = list(uploads.glob(f"{body.petition_id}_*.pdf"))
        if not matches:
            matches = list(uploads.glob(f"*{body.petition_id}*.pdf"))
        if not matches:
            raise HTTPException(status_code=404, detail="Petição não encontrada em uploads/.")
        petition_path = matches[0]
    try:
        result = container.measure_analysis_time_use_case.execute(
            chunks=chunks,
            documents=documents,
            embeddings=embeddings,
            runs=body.runs,
            petition_path=petition_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MeasureAnalysisTimeResponse(
        petition_name=result["petition_name"],
        runs=result["runs"],
        mean_seconds=result["mean_seconds"],
        mean_label=result["mean_label"],
        items=[_analysis_time_to_out(item) for item in result["items"]],
    )


def _analysis_time_to_out(entry) -> AnalysisTimeOut:
    return AnalysisTimeOut(
        entry_id=entry.entry_id,
        petition_name=entry.petition_name,
        seconds=entry.seconds,
        label=format_seconds(entry.seconds),
        created_at=entry.created_at,
        source=entry.source,
    )


def _reading_time_to_out(entry: ReadingTimeEntry) -> ReadingTimeOut:
    return ReadingTimeOut(
        entry_id=entry.entry_id,
        lawyer_name=entry.lawyer_name,
        minutes=entry.minutes,
        label=format_minutes(entry.minutes),
        created_at=entry.created_at,
    )


@router.get(
    "/v1/validations/{validation_id}",
    response_model=HumanValidationOut,
    tags=["validation"],
    summary="Obtém uma validação humana pelo ID",
)
def get_human_validation(
    validation_id: str,
    container: AppContainer = Depends(get_container),
) -> HumanValidationOut:
    validation = container.get_human_validation_use_case.execute(validation_id)
    if validation is None:
        raise HTTPException(status_code=404, detail="Validação não encontrada.")
    return _validation_to_out(validation)


def _validation_to_out(validation: HumanValidation) -> HumanValidationOut:
    return HumanValidationOut(
        validation_id=validation.validation_id,
        petition_id=validation.petition_id,
        petition_name=validation.petition_name,
        reviewer_name=validation.reviewer_name,
        created_at=validation.created_at,
        prototype_scores=validation.prototype_scores,
        human_scores=validation.human_scores,
        problem_assessments=[
            ProblemAssessmentOut(
                problem=item.problem,
                verdict=item.verdict,
                note=item.note,
            )
            for item in validation.problem_assessments
        ],
        documentation_ok=validation.documentation_ok,
        textual_cohesion_ok=validation.textual_cohesion_ok,
        argumentative_consistency_ok=validation.argumentative_consistency_ok,
        legal_basis_ok=validation.legal_basis_ok,
        final_quality=validation.final_quality,
        comments=validation.comments,
        comparison=ComparisonOut(
            mae_scores=validation.comparison.mae_scores,
            agreement_rate=validation.comparison.agreement_rate,
            dimension_gaps=validation.comparison.dimension_gaps,
            problems_confirmed=validation.comparison.problems_confirmed,
            problems_partial=validation.comparison.problems_partial,
            problems_rejected=validation.comparison.problems_rejected,
            summary=validation.comparison.summary,
        ),
        markdown_report=validation.markdown_report,
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
    result = container.download_petitions_use_case.execute(on_progress=on_progress)
    return {
        "total_documents": result.total_documents,
        "new_accepted": result.new_accepted,
        "new_rejected": result.new_rejected,
        "new_partial": result.new_partial,
        "candidates_found": result.candidates_found,
        "message": result.message,
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
