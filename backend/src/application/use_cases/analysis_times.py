"""Use cases: tempos reais de análise da aplicação."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.application.use_cases.analyze_petition import AnalyzePetitionUseCase
from src.domain.entities import Chunk, DocumentSummary
from src.domain.validation import AnalysisTimeEntry
from src.infrastructure.persistence.analysis_time_repository_sqlite import (
    SQLiteAnalysisTimeRepository,
)


def format_seconds(seconds: float) -> str:
    """1.3 -> '1,3 s' · 0.034 -> '34 ms' · 65 -> '1m05s'."""
    if seconds < 1:
        ms = int(round(seconds * 1000))
        if ms < 1:
            return f"{seconds*1000:.1f} ms".replace(".", ",")
        return f"{ms} ms"
    if seconds < 60:
        return f"{seconds:.1f} s".replace(".", ",")
    minutes = int(seconds // 60)
    rem = int(round(seconds % 60))
    return f"{minutes}m{rem:02d}s"


class RecordAnalysisTimeUseCase:
    """Persiste uma medição de tempo da aplicação."""

    def __init__(self, repository: SQLiteAnalysisTimeRepository) -> None:
        self._repository = repository

    def execute(
        self,
        petition_name: str,
        seconds: float,
        source: str = "auto",
    ) -> AnalysisTimeEntry:
        entry = AnalysisTimeEntry(
            entry_id=uuid.uuid4().hex[:12],
            petition_name=petition_name,
            seconds=round(float(seconds), 3),
            created_at=datetime.now(timezone.utc).isoformat(),
            source=source,
        )
        self._repository.save(entry)
        return entry


class ListAnalysisTimesUseCase:
    """Lista medições e agrega a média real da aplicação."""

    def __init__(self, repository: SQLiteAnalysisTimeRepository) -> None:
        self._repository = repository

    def execute(self) -> tuple[list[AnalysisTimeEntry], dict]:
        items = self._repository.list_all()
        if not items:
            return [], {
                "count": 0,
                "mean_seconds": None,
                "mean_label": None,
            }
        mean = sum(item.seconds for item in items) / len(items)
        return items, {
            "count": len(items),
            "mean_seconds": round(mean, 3),
            "mean_label": format_seconds(mean),
        }


class MeasureAnalysisTimeUseCase:
    """Executa N análises reais e grava os tempos (botão do dashboard)."""

    def __init__(
        self,
        analyze: AnalyzePetitionUseCase,
        repository: SQLiteAnalysisTimeRepository,
        uploads_dir: Path,
    ) -> None:
        self._analyze = analyze
        self._repository = repository
        self._uploads_dir = uploads_dir

    def execute(
        self,
        chunks: list[Chunk],
        documents: list[DocumentSummary],
        embeddings: np.ndarray,
        runs: int = 3,
        petition_path: Path | None = None,
    ) -> dict:
        pdf = petition_path or self._pick_sample_pdf()
        if pdf is None or not pdf.exists():
            raise ValueError(
                "Nenhuma petição em uploads/ para medir. "
                "Anexe uma petição no chat ou informe petition_id."
            )

        recorder = RecordAnalysisTimeUseCase(self._repository)
        measured: list[AnalysisTimeEntry] = []
        # Warm-up (não grava) — carrega modelo de embeddings sem contaminar a média
        self._analyze.execute(
            pdf, chunks, documents, embeddings, record_time=False
        )

        for _ in range(max(1, int(runs))):
            t0 = time.perf_counter()
            self._analyze.execute(
                pdf, chunks, documents, embeddings, record_time=False
            )
            elapsed = time.perf_counter() - t0
            measured.append(
                recorder.execute(
                    petition_name=pdf.name,
                    seconds=elapsed,
                    source="measure",
                )
            )

        mean = sum(item.seconds for item in measured) / len(measured)
        return {
            "petition_name": pdf.name,
            "runs": len(measured),
            "items": measured,
            "mean_seconds": round(mean, 3),
            "mean_label": format_seconds(mean),
        }

    def _pick_sample_pdf(self) -> Path | None:
        if not self._uploads_dir.exists():
            return None
        pdfs = [
            path
            for path in self._uploads_dir.glob("*.pdf")
            if "prompt_malicioso" not in path.name.lower()
            and path.stat().st_size >= 80_000  # evita PDFs minúsculos/decisões curtas
        ]
        if not pdfs:
            pdfs = [
                path
                for path in self._uploads_dir.glob("*.pdf")
                if "prompt_malicioso" not in path.name.lower()
            ]
        if not pdfs:
            return None
        # Prefere petições "030-kelly..." se existirem; senão o maior arquivo.
        preferred = [p for p in pdfs if "kelly" in p.name.lower() or "peticao" in p.name.lower()]
        pool = preferred or pdfs
        return max(pool, key=lambda path: path.stat().st_size)
