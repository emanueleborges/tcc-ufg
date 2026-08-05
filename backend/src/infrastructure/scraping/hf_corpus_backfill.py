"""Backfill do corpus a partir de datasets públicos (Hugging Face).

Usado quando a busca web de PDFs falha e o acervo fica abaixo da meta,
ou quando faltam rejeitadas/parciais para contraste trinário.

Fontes:
- ``stadv/modelos_peticoes`` — modelos de petição (texto público)
- ``mrhewbuc/brazilian_court_civil_decisions`` — decisões cíveis com rótulo
"""

from __future__ import annotations

import hashlib
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.domain.entities import SavedDocument
from src.infrastructure.nlp.case_outcome import classify_outcome
from src.infrastructure.nlp.text_utils import safe_file_name

_HF_ROWS = "https://datasets-server.huggingface.co/rows"
_PETITION_KEYWORDS = (
    "dano moral",
    "danos morais",
    "indeniza",
    "petição inicial",
    "peticao inicial",
    "negativa",
    "serasa",
    "consumidor",
)
_DECISION_KEYWORDS = (
    "dano moral",
    "danos morais",
    "indeniza",
    "moral",
)


def backfill_from_open_datasets(
    *,
    accepted_dir: Path,
    rejected_dir: Path,
    partial_dir: Path,
    saved: list[SavedDocument],
    existing_hashes: set[str],
    target_total: int,
    user_agent: str,
    on_progress=None,
) -> tuple[int, int, int]:
    """Gera PDFs até meta total + contraste rejeitadas/parciais.

    Returns:
        (new_accepted, new_rejected, new_partial)
    """
    current = (
        len(list(accepted_dir.glob("*.pdf")))
        + len(list(rejected_dir.glob("*.pdf")))
        + len(list(partial_dir.glob("*.pdf")))
    )
    rejected_now = len(list(rejected_dir.glob("*.pdf")))
    partial_now = len(list(partial_dir.glob("*.pdf")))
    missing = max(0, target_total - current)
    min_rejected = max(20, target_total // 4)
    min_partial = max(15, target_total // 7)
    need_rejected = max(0, min_rejected - rejected_now)
    need_partial = max(0, min_partial - partial_now)

    if missing <= 0 and need_rejected <= 0 and need_partial <= 0:
        return 0, 0, 0

    print(
        f"Backfill HF: faltam {missing} docs (meta {target_total}); "
        f"rejeitadas +{need_rejected}; parcial +{need_partial}.",
        file=sys.stderr,
    )
    if on_progress:
        on_progress(85, "Completando corpus com datasets públicos…")

    new_accepted = 0
    new_rejected = 0
    new_partial = 0
    seen_hashes = set(existing_hashes)
    budget = max(missing, need_rejected + need_partial)

    # 1) Improcedentes → rejeitadas/
    if need_rejected > 0:
        for row in _iter_hf_rows(
            "mrhewbuc/brazilian_court_civil_decisions",
            user_agent=user_agent,
            page_size=100,
            max_rows=1500,
        ):
            if new_rejected >= need_rejected:
                break
            added = _try_persist_decision_row(
                row,
                force_status="rejeitada",
                accepted_dir=accepted_dir,
                rejected_dir=rejected_dir,
                partial_dir=partial_dir,
                saved=saved,
                seen_hashes=seen_hashes,
            )
            if added == "rejeitada":
                new_rejected += 1

    # 2) Parciais → parcial/
    if need_partial > 0:
        for row in _iter_hf_rows(
            "mrhewbuc/brazilian_court_civil_decisions",
            user_agent=user_agent,
            page_size=100,
            max_rows=1500,
        ):
            if new_partial >= need_partial:
                break
            added = _try_persist_decision_row(
                row,
                force_status="parcial",
                accepted_dir=accepted_dir,
                rejected_dir=rejected_dir,
                partial_dir=partial_dir,
                saved=saved,
                seen_hashes=seen_hashes,
            )
            if added == "parcial":
                new_partial += 1

    # 3) Modelos de petição para volume
    if new_accepted + new_rejected + new_partial < missing:
        for row in _iter_hf_rows(
            "stadv/modelos_peticoes",
            user_agent=user_agent,
            page_size=100,
            max_rows=400,
        ):
            if new_accepted + new_rejected + new_partial >= missing:
                break
            title = str(row.get("titulo") or "modelo-peticao")
            content = str(row.get("conteudo") or "").strip()
            fonte = str(row.get("fonte") or "huggingface:stadv/modelos_peticoes")
            if len(content) < 400:
                continue
            blob = f"{title}\n{content}".lower()
            if not any(k in blob for k in _PETITION_KEYWORDS):
                continue
            outcome = classify_outcome(f"{title}\n{content}")
            if outcome == "indeferido":
                status = "rejeitada"
            elif outcome == "parcial":
                status = "parcial"
            else:
                status = "aceita"
            ok = _persist_text_pdf(
                title=title,
                body=content,
                source_url=fonte,
                source_query="hf:modelos_peticoes",
                outcome=outcome,
                status=status,
                accepted_dir=accepted_dir,
                rejected_dir=rejected_dir,
                partial_dir=partial_dir,
                saved=saved,
                seen_hashes=seen_hashes,
            )
            if not ok:
                continue
            if status == "rejeitada":
                new_rejected += 1
            elif status == "parcial":
                new_partial += 1
            else:
                new_accepted += 1

    # 4) Demais decisões para fechar volume
    if new_accepted + new_rejected + new_partial < max(missing, budget):
        for row in _iter_hf_rows(
            "mrhewbuc/brazilian_court_civil_decisions",
            user_agent=user_agent,
            page_size=100,
            max_rows=1500,
        ):
            if new_accepted + new_rejected + new_partial >= max(missing, budget):
                break
            added = _try_persist_decision_row(
                row,
                force_status=None,
                accepted_dir=accepted_dir,
                rejected_dir=rejected_dir,
                partial_dir=partial_dir,
                saved=saved,
                seen_hashes=seen_hashes,
            )
            if added == "rejeitada":
                new_rejected += 1
            elif added == "parcial":
                new_partial += 1
            elif added == "aceita":
                new_accepted += 1

    print(
        f"Backfill HF: +{new_accepted} aceitas, +{new_rejected} rejeitadas, "
        f"+{new_partial} parcial.",
        file=sys.stderr,
    )
    return new_accepted, new_rejected, new_partial


def _try_persist_decision_row(
    row: dict,
    *,
    force_status: Optional[str],
    accepted_dir: Path,
    rejected_dir: Path,
    partial_dir: Path,
    saved: list[SavedDocument],
    seen_hashes: set[str],
) -> Optional[str]:
    ementa = str(row.get("ementa_text") or "")
    decision = str(row.get("decision_description") or "")
    judgment = str(row.get("judgment_text") or "")
    label = str(row.get("judgment_label") or "").strip().lower()
    process_number = str(row.get("process_number") or "sem-numero")
    blob = f"{ementa}\n{decision}\n{judgment}".lower()
    if not any(k in blob for k in _DECISION_KEYWORDS):
        return None
    if label not in {"yes", "no", "partial"}:
        return None

    if force_status == "rejeitada":
        if label != "no":
            return None
        status, outcome = "rejeitada", "indeferido"
    elif force_status == "parcial":
        if label != "partial":
            return None
        status, outcome = "parcial", "parcial"
    elif label == "no":
        status, outcome = "rejeitada", "indeferido"
    elif label == "partial":
        status, outcome = "parcial", "parcial"
    else:
        status, outcome = "aceita", "deferido"

    title = f"Decisão {process_number} ({label})"
    body = "\n\n".join(
        part
        for part in (
            f"Processo: {process_number}",
            f"Órgão: {row.get('orgao_julgador') or ''}",
            f"Relator: {row.get('judge_relator') or ''}",
            f"Data: {row.get('publish_date') or ''}",
            f"Julgamento: {judgment}",
            f"Rótulo: {label}",
            ementa,
            decision,
        )
        if part and str(part).strip()
    )
    fonte = (
        "huggingface:mrhewbuc/brazilian_court_civil_decisions#"
        + quote(process_number, safe="")
    )
    ok = _persist_text_pdf(
        title=title,
        body=body,
        source_url=fonte,
        source_query="hf:brazilian_court_civil_decisions",
        outcome=outcome,
        status=status,
        accepted_dir=accepted_dir,
        rejected_dir=rejected_dir,
        partial_dir=partial_dir,
        saved=saved,
        seen_hashes=seen_hashes,
    )
    return status if ok else None


def _iter_hf_rows(
    dataset: str,
    *,
    user_agent: str,
    page_size: int,
    max_rows: int,
):
    offset = 0
    while offset < max_rows:
        try:
            response = requests.get(
                _HF_ROWS,
                params={
                    "dataset": dataset,
                    "config": "default",
                    "split": "train",
                    "offset": offset,
                    "length": min(page_size, max_rows - offset),
                },
                headers={"User-Agent": user_agent},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            print(f"Aviso: HF {dataset} offset={offset} falhou: {exc}", file=sys.stderr)
            break
        rows = payload.get("rows") or []
        if not rows:
            break
        for item in rows:
            row = item.get("row") if isinstance(item, dict) else None
            if isinstance(row, dict):
                yield row
        offset += len(rows)
        time.sleep(0.15)


def _persist_text_pdf(
    *,
    title: str,
    body: str,
    source_url: str,
    source_query: str,
    outcome: str,
    status: str,
    accepted_dir: Path,
    rejected_dir: Path,
    partial_dir: Path,
    saved: list[SavedDocument],
    seen_hashes: set[str],
) -> bool:
    pdf_bytes = _text_to_pdf_bytes(title=title, body=body)
    if not pdf_bytes:
        return False
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if digest in seen_hashes:
        return False
    seen_hashes.add(digest)

    base = safe_file_name(title)[:80] or digest[:12]
    if status == "rejeitada":
        path = rejected_dir / f"hf-{base}-{digest[:8]}.pdf"
    elif status == "parcial":
        path = partial_dir / f"hf-{base}-{digest[:8]}.pdf"
    else:
        idx = len(list(accepted_dir.glob("*.pdf"))) + 1
        path = accepted_dir / f"{idx:03d}-hf-{base}-{digest[:8]}.pdf"
    path.write_bytes(pdf_bytes)
    saved.append(
        SavedDocument(
            file_name=path.name,
            url=source_url,
            source_query=source_query,
            title=title,
            score=5,
            matched_terms=["huggingface-backfill"],
            sha256=digest,
            outcome=outcome,
            status=status,
        )
    )
    return True


def _text_to_pdf_bytes(*, title: str, body: str) -> Optional[bytes]:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _width, height = A4
    margin = 40
    y = height - margin
    pdf.setTitle(title[:200])
    pdf.setFont("Helvetica-Bold", 11)
    for line in _wrap(title, 90):
        if y < margin:
            pdf.showPage()
            y = height - margin
            pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, y, line)
        y -= 14
    y -= 8
    pdf.setFont("Helvetica", 9)
    for line in _wrap(body, 100):
        if y < margin:
            pdf.showPage()
            y = height - margin
            pdf.setFont("Helvetica", 9)
        safe = line.encode("latin-1", errors="replace").decode("latin-1")
        pdf.drawString(margin, y, safe)
        y -= 12
    pdf.save()
    return buffer.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in (text or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if len(trial) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines
