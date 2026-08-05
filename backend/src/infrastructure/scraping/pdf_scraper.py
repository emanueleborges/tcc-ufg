"""Scraper de PDFs jurídicos públicos para alimentar a base RAG.

Responsabilidade: buscar candidatos na internet, baixar PDFs reais,
filtrar documentos com indícios jurídicos e evitar duplicados.
Busca HTML-first (DuckDuckGo/Brave); DDGS opcional.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from tqdm import tqdm

from src.config.settings import PathsSettings, ScrapingSettings
from src.domain.entities import SavedDocument, ScrapingCandidate, ScrapingResult
from src.domain.patterns import FAVORABLE_TERMS, NEGATIVE_TERMS, PETITION_TERMS
from src.infrastructure.nlp.case_outcome import classify_outcome
from src.infrastructure.nlp.text_utils import contains_any, safe_file_name
from src.infrastructure.scraping.builtin_seeds import BUILTIN_PDF_URLS
from src.infrastructure.scraping.hf_corpus_backfill import backfill_from_open_datasets

_PDF_EXTENSION = ".pdf"
_METADATA_FIELDS = [
    "file_name",
    "url",
    "source_query",
    "title",
    "score",
    "matched_terms",
    "sha256",
    "outcome",
    "status",
]
_PDF_LINK_HINTS = ("pdf", "baixar", "download", "inteiro teor", "arquivo")
_PETITION_LINK_HINTS = (
    "petição",
    "peticao",
    "inicial",
    "dano moral",
    "danos morais",
    "sentença",
    "sentenca",
    "acórdão",
    "acordao",
    "improcedente",
    "procedente",
)
_LEGAL_HOST_HINTS = (
    ".jus.br",
    "conjur.com.br",
    "migalhas.com.br",
    "stj.jus.br",
    "mp.br",
    "mpdft",
    "mpsp",
)


class PdfScraper:
    """Fluxo completo: pesquisa, descoberta, download, filtragem, persistência."""

    def __init__(
        self,
        paths: PathsSettings,
        settings: ScrapingSettings,
    ) -> None:
        self._paths = paths
        self._settings = settings

    def run(self, on_progress: Callable[[int, str], None] | None = None) -> ScrapingResult:
        """Executa o pipeline. Grava aceitas, rejeitadas e parcial, sem duplicar."""

        def report(percent: int, message: str) -> None:
            if on_progress:
                on_progress(max(0, min(100, percent)), message)

        output_dir = self._paths.downloads_dir.expanduser().resolve()
        accepted_dir = self._paths.accepted_pdfs_dir
        rejected_dir = self._paths.rejected_pdfs_dir
        partial_dir = self._paths.partial_pdfs_dir
        accepted_dir.mkdir(parents=True, exist_ok=True)
        rejected_dir.mkdir(parents=True, exist_ok=True)
        partial_dir.mkdir(parents=True, exist_ok=True)

        deadline = self._build_deadline()
        existing = self._load_existing_metadata(output_dir)
        saved = list(existing)
        existing_hashes = {item.sha256 for item in existing if item.sha256}
        existing_hashes.update(
            _collect_disk_hashes(accepted_dir, rejected_dir, partial_dir)
        )
        existing_urls = {_dedupe_url(item.url) for item in existing if item.url}

        moved = _reclassify_existing_library(
            accepted_dir, rejected_dir, partial_dir, saved
        )
        if moved:
            print(f"Reclassificados entre pastas: {moved}")
            existing_hashes = {item.sha256 for item in saved if item.sha256}
            existing_hashes.update(
                _collect_disk_hashes(accepted_dir, rejected_dir, partial_dir)
            )

        current_total = (
            len(list(accepted_dir.glob("*.pdf")))
            + len(list(rejected_dir.glob("*.pdf")))
            + len(list(partial_dir.glob("*.pdf")))
        )
        gap_to_min = max(0, self._settings.min_corpus_size - current_total)
        target = max(int(self._settings.download_limit), gap_to_min, 1)
        print(
            f"Documentos no disco: {current_total} "
            f"(meta mínima {self._settings.min_corpus_size})"
        )
        print(f"Documentos já registrados: {len(existing)}")
        print(
            f"Meta desta execução: até {target} PDFs novos "
            f"(aceitas + rejeitadas + parcial)."
        )
        report(3, "Buscando candidatos na internet…")
        print("Buscando candidatos (HTML DuckDuckGo/Brave + seeds)...")
        candidates = self._search_candidates(
            output_dir=output_dir, deadline=deadline, on_progress=report
        )
        print(f"Encontrados {len(candidates)} resultados iniciais.")

        if not candidates:
            message = (
                "Nenhum resultado de busca e sem seeds utilizáveis. "
                f"Base atual: {current_total} docs. "
                "Adicione URLs em downloads_peticoes/seed_urls.txt."
            )
            print(message, file=sys.stderr)
            report(100, message)
            return ScrapingResult(
                total_documents=len(saved),
                new_accepted=0,
                new_rejected=0,
                new_partial=0,
                candidates_found=0,
                message=message,
            )

        report(25, "Descobrindo links de PDF…")
        expanded = self._expand_candidates(
            candidates, existing_urls, deadline, on_progress=report
        )
        expanded = [
            item for item in expanded if _dedupe_url(item.url) not in existing_urls
        ]
        print(f"Analisando {len(expanded)} possíveis PDFs novos...")

        report(50, "Baixando e filtrando PDFs…")
        new_accepted, new_rejected, new_partial = self._download_and_filter(
            expanded=expanded,
            saved=saved,
            existing_hashes=existing_hashes,
            existing_urls=existing_urls,
            output_dir=output_dir,
            accepted_dir=accepted_dir,
            rejected_dir=rejected_dir,
            partial_dir=partial_dir,
            deadline=deadline,
            download_target=target,
            on_progress=report,
        )

        disk_total = (
            len(list(accepted_dir.glob("*.pdf")))
            + len(list(rejected_dir.glob("*.pdf")))
            + len(list(partial_dir.glob("*.pdf")))
        )
        rejected_count = len(list(rejected_dir.glob("*.pdf")))
        partial_count = len(list(partial_dir.glob("*.pdf")))
        min_rejected = max(20, self._settings.min_corpus_size // 4)
        min_partial = max(15, self._settings.min_corpus_size // 7)
        needs_backfill = (
            disk_total < self._settings.min_corpus_size
            or rejected_count < min_rejected
            or partial_count < min_partial
        )
        if needs_backfill:
            report(85, "Completando corpus com datasets públicos…")
            existing_hashes.update({item.sha256 for item in saved if item.sha256})
            bf_accepted, bf_rejected, bf_partial = backfill_from_open_datasets(
                accepted_dir=accepted_dir,
                rejected_dir=rejected_dir,
                partial_dir=partial_dir,
                saved=saved,
                existing_hashes=existing_hashes,
                target_total=self._settings.min_corpus_size,
                user_agent=self._settings.user_agent,
                on_progress=report,
            )
            new_accepted += bf_accepted
            new_rejected += bf_rejected
            new_partial += bf_partial

        report(97, "Salvando metadados…")
        self._save_metadata(output_dir, saved)
        total_new = new_accepted + new_rejected + new_partial
        disk_total = (
            len(list(accepted_dir.glob("*.pdf")))
            + len(list(rejected_dir.glob("*.pdf")))
            + len(list(partial_dir.glob("*.pdf")))
        )
        message = (
            f"Novos: {total_new} (aceitas={new_accepted}, "
            f"rejeitadas={new_rejected}, parcial={new_partial}). "
            f"Total na base: {disk_total}."
        )
        print(message)
        print(f"Aceitas em: {accepted_dir}")
        print(f"Rejeitadas em: {rejected_dir}")
        print(f"Parcial em: {partial_dir}")
        if disk_total < self._settings.min_corpus_size:
            print(
                f"Aviso: corpus ainda abaixo de {self._settings.min_corpus_size} "
                f"({disk_total}).",
                file=sys.stderr,
            )
        report(100, message)
        return ScrapingResult(
            total_documents=len(saved),
            new_accepted=new_accepted,
            new_rejected=new_rejected,
            new_partial=new_partial,
            candidates_found=len(candidates),
            message=message,
        )

    def _build_deadline(self) -> Optional[float]:
        if not self._settings.max_runtime_seconds:
            return None
        return time.monotonic() + self._settings.max_runtime_seconds

    def _search_candidates(
        self,
        *,
        output_dir: Path,
        deadline: Optional[float],
        on_progress: Callable[[int, str], None] | None = None,
    ) -> list[ScrapingCandidate]:
        candidates: list[ScrapingCandidate] = []
        seen: set[str] = set()

        # Seeds primeiro: não dependem de buscador.
        for seed in _load_seed_candidates(output_dir):
            url = _dedupe_url(seed.url)
            if not url or url in seen:
                continue
            seen.add(url)
            candidates.append(seed)
        print(f"Seeds carregadas: {len(candidates)}")

        queries = list(self._settings.queries)
        total_queries = max(len(queries), 1)
        consecutive_misses = 0

        for query_index, query in enumerate(queries):
            if _deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante as consultas.")
                break
            if on_progress:
                percent = 5 + int((query_index / total_queries) * 20)
                on_progress(percent, f"Buscando query {query_index + 1}/{total_queries}")

            results = _search_web(
                query=query,
                max_results=self._settings.max_results,
                user_agent=self._settings.user_agent,
                timeout=self._settings.http_timeout,
                use_ddgs=self._settings.use_ddgs,
            )
            if not results:
                consecutive_misses += 1
                print(f"Aviso: sem resultados para {query!r}", file=sys.stderr)
                # Buscadores bloqueados (403/429): não gastar a execução inteira.
                if consecutive_misses >= 3 and len(candidates) > 0:
                    print(
                        "Busca web indisponível; seguindo só com seeds/candidatos já obtidos.",
                        file=sys.stderr,
                    )
                    break
            else:
                consecutive_misses = 0
            for result in results:
                url = result.get("href") or result.get("url") or ""
                url = _normalize_candidate_url(url)
                url = _dedupe_url(url)
                if not url or url in seen:
                    continue
                seen.add(url)
                candidates.append(
                    ScrapingCandidate(
                        url=url,
                        source_query=query,
                        title=result.get("title", ""),
                        snippet=result.get("body", "") or result.get("snippet", ""),
                    )
                )
            time.sleep(self._settings.search_pause)
        return candidates

    def _expand_candidates(
        self,
        candidates: list[ScrapingCandidate],
        existing_urls: set[str],
        deadline: Optional[float],
        on_progress: Callable[[int, str], None] | None = None,
    ) -> list[ScrapingCandidate]:
        expanded: list[ScrapingCandidate] = []
        seen_urls = set(existing_urls)
        total = max(len(candidates), 1)
        for index, candidate in enumerate(tqdm(candidates, desc="Descobrindo links")):
            if _deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante a descoberta de links.")
                break
            if on_progress:
                percent = 25 + int((index / total) * 25)
                on_progress(percent, f"Descobrindo links ({index + 1}/{total})")
            for link in self._discover_download_links(candidate):
                deduped = _dedupe_url(link.url)
                if deduped in seen_urls:
                    continue
                seen_urls.add(deduped)
                expanded.append(
                    ScrapingCandidate(
                        url=deduped,
                        source_query=link.source_query,
                        title=link.title,
                        snippet=link.snippet,
                    )
                )
        return expanded

    def _discover_download_links(
        self, candidate: ScrapingCandidate
    ) -> list[ScrapingCandidate]:
        if _looks_like_pdf_url(candidate.url):
            return [candidate]
        response = _request_get(
            candidate.url, self._settings.http_timeout, self._settings.user_agent
        )
        if not response:
            return []
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type:
            return [candidate]
        if "text/html" not in content_type and "xhtml" not in content_type:
            return []
        try:
            html = response.content[:2_000_000].decode(
                response.encoding or "utf-8", errors="ignore"
            )
        except Exception:  # noqa: BLE001
            return []

        soup = BeautifulSoup(html, "html.parser")
        links: list[ScrapingCandidate] = []
        seen: set[str] = set()
        host_legal = _looks_like_legal_host(candidate.url)
        for tag in soup.select("a[href]"):
            href = tag.get("href")
            if not href:
                continue
            absolute = _dedupe_url(urljoin(candidate.url, href))
            if absolute in seen:
                continue
            anchor_text = tag.get_text(" ", strip=True)
            likely_pdf = _looks_like_pdf_url(absolute) or contains_any(
                f"{anchor_text} {absolute}", _PDF_LINK_HINTS
            )
            likely_petition = contains_any(
                f"{anchor_text} {absolute} {candidate.title} {candidate.snippet}",
                _PETITION_LINK_HINTS,
            )
            # PDF direto entra; em páginas jurídicas, basta indício de download.
            if likely_pdf and (
                _looks_like_pdf_url(absolute) or likely_petition or host_legal
            ):
                seen.add(absolute)
                links.append(
                    ScrapingCandidate(
                        url=absolute,
                        source_query=candidate.source_query,
                        title=anchor_text or candidate.title,
                        snippet=candidate.snippet,
                    )
                )
            if len(links) >= self._settings.max_links_per_page:
                break
        return links

    def _download_and_filter(
        self,
        *,
        expanded: list[ScrapingCandidate],
        saved: list[SavedDocument],
        existing_hashes: set[str],
        existing_urls: set[str],
        output_dir: Path,
        accepted_dir: Path,
        rejected_dir: Path,
        partial_dir: Path,
        deadline: Optional[float],
        download_target: int,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> tuple[int, int, int]:
        new_accepted = 0
        new_rejected = 0
        new_partial = 0
        seen_hashes = set(existing_hashes)
        seen_urls = set(existing_urls)
        total = max(len(expanded), 1)
        for index, candidate in enumerate(tqdm(expanded, desc="Baixando e filtrando")):
            if _deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante os downloads.")
                break
            if (new_accepted + new_rejected + new_partial) >= download_target:
                break

            url_key = _dedupe_url(candidate.url)
            if url_key in seen_urls:
                continue

            if on_progress:
                percent = 50 + int((index / total) * 45)
                on_progress(
                    percent,
                    (
                        f"Baixando PDFs ({index + 1}/{total}) · "
                        f"novos {new_accepted + new_rejected + new_partial}/{download_target} "
                        f"(aceitas={new_accepted}, rejeitadas={new_rejected}, "
                        f"parcial={new_partial})"
                    ),
                )
            data, content_type = self._download_pdf_bytes(candidate.url)
            if not data:
                continue
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 in seen_hashes:
                seen_urls.add(url_key)
                continue
            seen_hashes.add(sha256)
            seen_urls.add(url_key)

            base_name = safe_file_name(
                candidate.title
                or Path(urlparse(candidate.url).path).stem
                or sha256[:12]
            )
            temp_path = output_dir / f"tmp-{sha256[:12]}.pdf"
            temp_path.write_bytes(data)
            text = _extract_text(temp_path, content_type)
            keep, score, matched_terms, outcome, status = _classify_for_corpus(
                text, candidate.title, candidate.snippet, candidate.url
            )
            if not keep:
                temp_path.unlink(missing_ok=True)
                continue

            if status == "rejeitada":
                final_path = rejected_dir / f"{base_name}-{sha256[:8]}.pdf"
                new_rejected += 1
            elif status == "parcial":
                final_path = partial_dir / f"{base_name}-{sha256[:8]}.pdf"
                new_partial += 1
            else:
                final_path = (
                    accepted_dir
                    / f"{_next_index(accepted_dir):03d}-{base_name}-{sha256[:8]}.pdf"
                )
                new_accepted += 1

            temp_path.replace(final_path)
            saved.append(
                SavedDocument(
                    file_name=final_path.name,
                    url=candidate.url,
                    source_query=candidate.source_query,
                    title=candidate.title,
                    score=score,
                    matched_terms=matched_terms,
                    sha256=sha256,
                    outcome=outcome,
                    status=status,
                )
            )
            time.sleep(self._settings.request_pause)
        return new_accepted, new_rejected, new_partial

    def _download_pdf_bytes(self, url: str) -> tuple[Optional[bytes], str]:
        response = _request_get(
            url, self._settings.http_timeout, self._settings.user_agent
        )
        if not response:
            return None, ""
        content_type = response.headers.get("content-type", "").lower()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self._settings.max_file_size_bytes:
            return None, content_type
        chunks: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self._settings.max_file_size_bytes:
                    return None, content_type
                chunks.append(chunk)
        except requests.RequestException:
            return None, content_type
        data = b"".join(chunks)
        if not _is_pdf_data(data, content_type):
            return None, content_type
        return data, content_type

    @staticmethod
    def _load_existing_metadata(output_dir: Path) -> list[SavedDocument]:
        json_path = output_dir / "metadata.json"
        if not json_path.exists():
            return []
        try:
            rows = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        documents: list[SavedDocument] = []
        for row in rows:
            try:
                documents.append(
                    SavedDocument(
                        file_name=str(row.get("file_name", "")),
                        url=str(row.get("url", "")),
                        source_query=str(row.get("source_query", "")),
                        title=str(row.get("title", "")),
                        score=int(row.get("score", 0)),
                        matched_terms=list(row.get("matched_terms", [])),
                        sha256=str(row.get("sha256", "")),
                        outcome=str(row.get("outcome", "indefinido") or "indefinido"),
                        status=str(row.get("status", "aceita") or "aceita"),
                    )
                )
            except (TypeError, ValueError):
                continue
        return documents

    @staticmethod
    def _save_metadata(output_dir: Path, saved: list[SavedDocument]) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "metadata.json"
        csv_path = output_dir / "metadata.csv"
        json_path.write_text(
            json.dumps([asdict(item) for item in saved], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=_METADATA_FIELDS)
            writer.writeheader()
            for item in saved:
                row = asdict(item)
                row["matched_terms"] = "; ".join(item.matched_terms)
                writer.writerow(row)


def _load_seed_candidates(output_dir: Path) -> list[ScrapingCandidate]:
    """Lê seeds embutidas + ``seed_urls.txt`` (uma URL por linha)."""
    path = output_dir / "seed_urls.txt"
    if not path.exists():
        path.write_text(
            "# Uma URL de PDF por linha (http/https).\n"
            "# Use especialmente sentenças/acórdãos IMPROCEDENTES para preencher rejeitadas/.\n",
            encoding="utf-8",
        )

    seeds: list[ScrapingCandidate] = []
    seen: set[str] = set()

    def add(url: str, source: str) -> None:
        cleaned = _normalize_candidate_url(url.strip())
        key = _dedupe_url(cleaned)
        if not key or key in seen:
            return
        seen.add(key)
        seeds.append(
            ScrapingCandidate(
                url=cleaned,
                source_query=source,
                title=Path(urlparse(cleaned).path).name or "seed.pdf",
                snippet="seed",
            )
        )

    for url in BUILTIN_PDF_URLS:
        add(url, "builtin_seeds")
    for line in path.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        add(url, "seed_urls.txt")
    return seeds


def _deadline_reached(deadline: Optional[float]) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _reclassify_existing_library(
    accepted_dir: Path,
    rejected_dir: Path,
    partial_dir: Path,
    saved: list[SavedDocument],
) -> int:
    """Reorganiza PDFs entre aceitas/, rejeitadas/ e parcial/ conforme o outcome."""
    rejected_dir.mkdir(parents=True, exist_ok=True)
    partial_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    by_name = {item.file_name: item for item in saved}

    def _move(path: Path, target_dir: Path, outcome: str, status: str) -> None:
        nonlocal moved
        target = target_dir / path.name
        if target.exists():
            target = target_dir / f"moved-{path.name}"
        path.replace(target)
        moved += 1
        meta = by_name.get(path.name)
        if meta is not None:
            idx = saved.index(meta)
            saved[idx] = SavedDocument(
                file_name=target.name,
                url=meta.url,
                source_query=meta.source_query,
                title=meta.title,
                score=meta.score,
                matched_terms=meta.matched_terms,
                sha256=meta.sha256,
                outcome=outcome,
                status=status,
            )

    for path in list(accepted_dir.glob("*.pdf")):
        try:
            text = _extract_text(path, "application/pdf")
        except Exception:  # noqa: BLE001
            continue
        outcome = classify_outcome(text)
        if outcome == "indeferido":
            _move(path, rejected_dir, "indeferido", "rejeitada")
        elif outcome == "parcial":
            _move(path, partial_dir, "parcial", "parcial")

    for path in list(partial_dir.glob("*.pdf")):
        try:
            text = _extract_text(path, "application/pdf")
        except Exception:  # noqa: BLE001
            continue
        outcome = classify_outcome(text)
        if outcome == "indeferido":
            _move(path, rejected_dir, "indeferido", "rejeitada")
        elif outcome == "deferido":
            _move(path, accepted_dir, "deferido", "aceita")

    for path in list(rejected_dir.glob("*.pdf")):
        try:
            text = _extract_text(path, "application/pdf")
        except Exception:  # noqa: BLE001
            continue
        outcome = classify_outcome(text)
        if outcome == "parcial":
            _move(path, partial_dir, "parcial", "parcial")
        elif outcome == "deferido":
            _move(path, accepted_dir, "deferido", "aceita")

    return moved


def _search_web(
    *,
    query: str,
    max_results: int,
    user_agent: str,
    timeout: int,
    use_ddgs: bool,
) -> list[dict]:
    """Busca HTML-first; DDGS só se SCRAPING_USE_DDGS=1."""
    # 1) DuckDuckGo HTML (mais estável que a lib DDGS neste ambiente)
    html_results = _search_duckduckgo_html(query, user_agent, timeout, max_results)
    if html_results:
        return html_results

    # 2) Brave HTML
    brave_results = _search_brave_html(query, user_agent, timeout, max_results)
    if brave_results:
        return brave_results

    # 3) DDGS opcional (costuma falhar por DNS nos backends)
    if use_ddgs:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore[no-redef]
            with DDGS() as ddgs:
                batch = ddgs.text(
                    query,
                    region="br-pt",
                    safesearch="moderate",
                    max_results=max_results,
                    backend="duckduckgo",
                )
            results = list(batch or [])
            if results:
                return results
        except Exception as exc:  # noqa: BLE001
            print(f"Aviso: DDGS falhou para {query!r}: {exc}", file=sys.stderr)

    return []


def _search_duckduckgo_html(
    query: str, user_agent: str, timeout: int, max_results: int
) -> list[dict]:
    try:
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={
                "User-Agent": user_agent,
                "Referer": "https://html.duckduckgo.com/",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Aviso: DDG HTML falhou: {exc}", file=sys.stderr)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []
    for item in soup.select(".result"):
        anchor = item.select_one("a.result__a")
        if not anchor or not anchor.get("href"):
            continue
        href = anchor["href"]
        snippet_el = item.select_one(".result__snippet")
        results.append(
            {
                "href": href,
                "title": anchor.get_text(" ", strip=True),
                "body": snippet_el.get_text(" ", strip=True) if snippet_el else "",
            }
        )
        if len(results) >= max_results:
            break
    return results


def _search_brave_html(
    query: str, user_agent: str, timeout: int, max_results: int
) -> list[dict]:
    try:
        response = requests.get(
            "https://search.brave.com/search",
            params={"q": query, "source": "web"},
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Aviso: Brave HTML falhou: {exc}", file=sys.stderr)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.select("div[data-type=web] a"):
        href = anchor.get("href") or ""
        if not href.startswith("http") or href in seen:
            continue
        seen.add(href)
        results.append(
            {
                "href": href,
                "title": anchor.get_text(" ", strip=True),
                "body": "",
            }
        )
        if len(results) >= max_results:
            break
    return results


def _next_index(directory: Path) -> int:
    existing = list(directory.glob("*.pdf"))
    return len(existing) + 1


def _collect_disk_hashes(*directories: Path) -> set[str]:
    """Hashes já presentes em disco (aceitas/rejeitadas), para não baixar de novo."""
    hashes: set[str] = set()
    for directory in directories:
        if not directory.exists():
            continue
        for path in directory.glob("*.pdf"):
            try:
                hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
            except OSError:
                continue
    return hashes


def _dedupe_url(url: str) -> str:
    return urldefrag(url)[0].rstrip("/").lower()


def _normalize_candidate_url(url: str) -> str:
    """Normaliza links de visualização (Plone/@@download, /view) para download."""
    cleaned = url.strip()
    if not cleaned:
        return cleaned
    lower = cleaned.lower()
    if lower.endswith("/view"):
        cleaned = cleaned[: -len("/view")]
    if "/@@download/file" not in lower and ".pdf" in lower and lower.endswith("/view"):
        cleaned = cleaned[: -len("/view")]
    # Plone: .../arquivo.pdf/view → .../arquivo.pdf
    if cleaned.lower().endswith(".pdf/view"):
        cleaned = cleaned[: -len("/view")]
    return cleaned


def _looks_like_pdf_url(url: str) -> bool:
    normalized = _normalize_candidate_url(url)
    parsed = urlparse(_dedupe_url(normalized))
    path = parsed.path.lower()
    query = parsed.query.lower()
    return (
        path.endswith(_PDF_EXTENSION)
        or ".pdf" in path
        or "filetype=pdf" in query
        or "getarquivo" in path
        or "inteiroteor" in path.replace("_", "").replace("-", "")
    )


def _looks_like_legal_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(hint in host for hint in _LEGAL_HOST_HINTS)


def _is_pdf_data(data: bytes, content_type: str) -> bool:
    return data.lstrip().startswith(b"%PDF") and "html" not in content_type.lower()


def _request_get(
    url: str, timeout: int, user_agent: str
) -> Optional[requests.Response]:
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        return response
    except requests.RequestException:
        return None


def _extract_text(file_path: Path, content_type: str) -> str:
    try:
        if file_path.suffix.lower() == ".pdf" or "pdf" in content_type:
            reader = PdfReader(str(file_path))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:30])
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _classify_for_corpus(
    text: str, title: str, snippet: str, url: str = ""
) -> tuple[bool, int, list[str], str, str]:
    """Decide se o PDF entra na base e em qual pasta.

    - ``aceitas/``: deferido / indefinido com sinal jurídico
    - ``rejeitadas/``: indeferido
    - ``parcial/``: parcialmente procedente
    - fora da base: PDF sem relevância jurídica mínima
    """
    searchable = f"{title}\n{snippet}\n{url}\n{text}"
    meta_blob = f"{title}\n{snippet}\n{url}"
    petition_matches = contains_any(searchable, PETITION_TERMS)
    favorable_matches = contains_any(text or meta_blob, FAVORABLE_TERMS)
    negative_matches = contains_any(text or meta_blob, NEGATIVE_TERMS)
    meta_legal = contains_any(
        meta_blob,
        PETITION_TERMS
        + FAVORABLE_TERMS
        + NEGATIVE_TERMS
        + ["dano moral", "danos morais", "indeniza", "sentença", "petição", "parcial"],
    )
    outcome = classify_outcome(searchable)

    score = (
        (len(petition_matches) * 2)
        + (len(favorable_matches) * 3)
        + (len(negative_matches) * 3)
        + (2 if meta_legal else 0)
        + (1 if _looks_like_legal_host(url) else 0)
    )
    has_decision_signal = bool(favorable_matches or negative_matches)
    legal_enough = bool(petition_matches) or has_decision_signal or meta_legal
    if not legal_enough or score < 1:
        return False, score, [], outcome, "descartada"

    matched = sorted(set(petition_matches + favorable_matches + negative_matches))
    if outcome == "indeferido":
        return True, score, matched, outcome, "rejeitada"
    if outcome == "parcial":
        return True, score, matched, outcome, "parcial"
    return True, score, matched, outcome, "aceita"


# Compatível com testes antigos.
def _evaluate_document(
    text: str, title: str, snippet: str
) -> tuple[bool, int, list[str], str]:
    keep, score, matched, outcome, status = _classify_for_corpus(
        text, title, snippet, ""
    )
    accepted = keep and status == "aceita"
    return accepted, score, matched, outcome
