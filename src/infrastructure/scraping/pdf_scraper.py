"""Scraper de PDFs jurídicos públicos para alimentar a base RAG.

Responsabilidade: buscar candidatos na internet, baixar PDFs reais,
filtrar documentos com indícios de procedência e evitar duplicados.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from tqdm import tqdm

try:
    from ddgs import DDGS
except ImportError:  # compatibilidade com versões antigas
    from duckduckgo_search import DDGS  # type: ignore[no-redef]

from src.config.settings import PathsSettings, ScrapingSettings
from src.domain.entities import SavedDocument, ScrapingCandidate
from src.domain.patterns import FAVORABLE_TERMS, NEGATIVE_TERMS, PETITION_TERMS
from src.infrastructure.nlp.text_utils import contains_any, safe_file_name

_PDF_EXTENSION = ".pdf"
_METADATA_FIELDS = [
    "file_name",
    "url",
    "source_query",
    "title",
    "score",
    "matched_terms",
    "sha256",
]
_PDF_LINK_HINTS = ("pdf", "baixar", "download", "inteiro teor")
_PETITION_LINK_HINTS = (
    "petição",
    "peticao",
    "inicial",
    "dano moral",
    "danos morais",
    "sentença",
    "sentenca",
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

    def run(self) -> int:
        """Executa o pipeline. Retorna o número total de PDFs aceitos na base."""
        output_dir = self._paths.downloads_dir.expanduser().resolve()
        accepted_dir = self._paths.accepted_pdfs_dir
        rejected_dir = self._paths.rejected_pdfs_dir
        accepted_dir.mkdir(parents=True, exist_ok=True)
        if self._settings.keep_rejected:
            rejected_dir.mkdir(parents=True, exist_ok=True)

        deadline = self._build_deadline()
        existing = self._load_existing_metadata(output_dir)
        saved = list(existing)
        existing_hashes = {item.sha256 for item in existing if item.sha256}
        existing_urls = {_dedupe_url(item.url) for item in existing if item.url}

        print(f"Documentos já registrados: {len(existing)}")
        print("Buscando candidatos na internet...")
        candidates = self._search_candidates(deadline)
        print(f"Encontrados {len(candidates)} resultados iniciais.")

        expanded = self._expand_candidates(candidates, existing_urls, deadline)
        print(f"Analisando {len(expanded)} possíveis PDFs novos...")

        new_saved_count = self._download_and_filter(
            expanded=expanded,
            saved=saved,
            existing_hashes=existing_hashes,
            output_dir=output_dir,
            accepted_dir=accepted_dir,
            rejected_dir=rejected_dir,
            deadline=deadline,
        )

        self._save_metadata(output_dir, saved)
        print(f"Concluído. Novos PDFs aceitos: {new_saved_count}")
        print(f"Total de PDFs registrados: {len(saved)}")
        print(f"Arquivos salvos em: {accepted_dir}")
        print(
            f"Metadados: {output_dir / 'metadata.json'} e "
            f"{output_dir / 'metadata.csv'}"
        )
        print("Revise manualmente os documentos antes de usar. O filtro é heurístico.")
        return len(saved)

    def _build_deadline(self) -> Optional[float]:
        if not self._settings.max_runtime_seconds:
            return None
        return time.monotonic() + self._settings.max_runtime_seconds

    def _search_candidates(self, deadline: Optional[float]) -> list[ScrapingCandidate]:
        candidates: list[ScrapingCandidate] = []
        seen: set[str] = set()
        with DDGS() as ddgs:
            for query in self._settings.queries:
                if _deadline_reached(deadline):
                    print("Tempo máximo de busca atingido durante as consultas.")
                    break
                try:
                    results = ddgs.text(
                        query,
                        region="br-pt",
                        safesearch="moderate",
                        max_results=self._settings.max_results,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Aviso: falha ao buscar por {query!r}: {exc}", file=sys.stderr)
                    continue
                for result in results:
                    url = result.get("href") or result.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    candidates.append(
                        ScrapingCandidate(
                            url=url,
                            source_query=query,
                            title=result.get("title", ""),
                            snippet=result.get("body", ""),
                        )
                    )
                time.sleep(self._settings.request_pause)
        return candidates

    def _expand_candidates(
        self,
        candidates: list[ScrapingCandidate],
        existing_urls: set[str],
        deadline: Optional[float],
    ) -> list[ScrapingCandidate]:
        expanded: list[ScrapingCandidate] = []
        seen_urls = set(existing_urls)
        for candidate in tqdm(candidates, desc="Descobrindo links"):
            if _deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante a descoberta de links.")
                break
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
        if "text/html" not in content_type:
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
            if likely_pdf and likely_petition:
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
        output_dir: Path,
        accepted_dir: Path,
        rejected_dir: Path,
        deadline: Optional[float],
    ) -> int:
        new_saved_count = 0
        seen_hashes = set(existing_hashes)
        for candidate in tqdm(expanded, desc="Baixando e filtrando"):
            if _deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante os downloads.")
                break
            if new_saved_count >= self._settings.download_limit:
                break
            data, content_type = self._download_pdf_bytes(candidate.url)
            if not data:
                continue
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 in seen_hashes:
                continue
            seen_hashes.add(sha256)

            base_name = safe_file_name(
                candidate.title
                or Path(urlparse(candidate.url).path).stem
                or sha256[:12]
            )
            temp_path = output_dir / f"tmp-{sha256[:12]}.pdf"
            temp_path.write_bytes(data)
            text = _extract_text(temp_path, content_type)
            accepted, score, matched_terms = _evaluate_document(
                text, candidate.title, candidate.snippet
            )
            if accepted:
                final_path = accepted_dir / f"{len(saved) + 1:03d}-{base_name}-{sha256[:8]}.pdf"
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
                    )
                )
                new_saved_count += 1
            elif self._settings.keep_rejected:
                temp_path.replace(rejected_dir / f"{base_name}-{sha256[:8]}.pdf")
            else:
                temp_path.unlink(missing_ok=True)
            time.sleep(self._settings.request_pause)
        return new_saved_count

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


def _deadline_reached(deadline: Optional[float]) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _dedupe_url(url: str) -> str:
    return urldefrag(url)[0]


def _looks_like_pdf_url(url: str) -> bool:
    parsed = urlparse(_dedupe_url(url))
    return parsed.path.lower().endswith(_PDF_EXTENSION) or ".pdf" in parsed.path.lower()


def _is_pdf_data(data: bytes, content_type: str) -> bool:
    return data.lstrip().startswith(b"%PDF") and "html" not in content_type.lower()


def _request_get(
    url: str, timeout: int, user_agent: str
) -> Optional[requests.Response]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": user_agent},
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


def _evaluate_document(
    text: str, title: str, snippet: str
) -> tuple[bool, int, list[str]]:
    searchable = f"{title}\n{snippet}\n{text}"
    petition_matches = contains_any(searchable, PETITION_TERMS)
    favorable_matches = contains_any(text, FAVORABLE_TERMS)
    negative_matches = contains_any(text, NEGATIVE_TERMS)
    score = (
        (len(petition_matches) * 2)
        + (len(favorable_matches) * 3)
        - (len(negative_matches) * 5)
    )
    accepted = (
        bool(petition_matches)
        and bool(favorable_matches)
        and not negative_matches
        and score >= 5
    )
    return accepted, score, sorted(set(petition_matches + favorable_matches))
