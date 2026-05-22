#!/usr/bin/env python3
"""Baixador de PDFs públicos para alimentar a base jurídica.

Responsabilidade deste script: buscar na internet, baixar somente PDFs reais,
filtrar documentos com indícios de ganho de causa e evitar duplicados.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from tqdm import tqdm

from legal_config import (
    ACCEPTED_PDFS_DIR,
    DOWNLOAD_LIMIT,
    DOWNLOADS_DIR,
    HTTP_TIMEOUT,
    KEEP_REJECTED,
    MAX_LINKS_PER_PAGE,
    MAX_RESULTS,
    MAX_RUNTIME_SECONDS,
    REJECTED_PDFS_DIR,
    REQUEST_PAUSE,
    SEARCH_QUERIES,
)

try:
    from ddgs import DDGS
except ImportError:  # compatibilidade com versões antigas do pacote
    from duckduckgo_search import DDGS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

PETITION_TERMS = [
    "petição inicial",
    "acao de indenizacao",
    "ação de indenização",
    "indenização por dano moral",
    "indenizacao por dano moral",
    "danos morais",
    "dano moral",
]

FAVORABLE_TERMS = [
    "julgo procedente",
    "julgo parcialmente procedente",
    "pedido procedente",
    "pedidos procedentes",
    "procedência do pedido",
    "procedencia do pedido",
    "ganho de causa",
    "sentença de procedência",
    "sentenca de procedencia",
    "recurso provido",
    "provimento ao recurso",
    "provimento parcial ao recurso",
]

NEGATIVE_TERMS = [
    "julgo improcedente",
    "pedido improcedente",
    "pedidos improcedentes",
    "improcedência do pedido",
    "improcedencia do pedido",
    "extingo o processo sem resolução do mérito",
    "extingo o processo sem resolucao do merito",
]

PDF_EXTENSION = ".pdf"
MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024
METADATA_FIELDS = ["file_name", "url", "source_query", "title", "score", "matched_terms", "sha256"]


@dataclass
class Candidate:
    url: str
    source_query: str
    title: str = ""
    snippet: str = ""


@dataclass
class SavedDocument:
    file_name: str
    url: str
    source_query: str
    title: str
    score: int
    matched_terms: list[str]
    sha256: str


def normalize_text(text: str) -> str:
    text = text.lower()
    replacements = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    return text.translate(replacements)


def contains_any(text: str, terms: Iterable[str]) -> list[str]:
    normalized = normalize_text(text)
    return [term for term in terms if normalize_text(term) in normalized]


def safe_file_name(text: str, default: str = "documento") -> str:
    text = normalize_text(text or default)
    text = re.sub(r"[^a-z0-9._-]+", "-", text).strip("-._")
    return (text[:90] or default).strip("-")


def dedupe_url(url: str) -> str:
    return urldefrag(url)[0]


def looks_like_pdf_url(url: str) -> bool:
    parsed = urlparse(dedupe_url(url))
    return parsed.path.lower().endswith(PDF_EXTENSION) or ".pdf" in parsed.path.lower()


def is_pdf_data(data: bytes, content_type: str) -> bool:
    return data.lstrip().startswith(b"%PDF") and "html" not in content_type.lower()


def request_get(url: str, timeout: int) -> Optional[requests.Response]:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        return response
    except requests.RequestException:
        return None


def deadline_reached(deadline: Optional[float]) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def search_candidates(queries: list[str], max_results_per_query: int, pause: float, deadline: Optional[float]) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    with DDGS() as ddgs:
        for query in queries:
            if deadline_reached(deadline):
                print("Tempo máximo de busca atingido durante as consultas.")
                break
            try:
                results = ddgs.text(query, region="br-pt", safesearch="moderate", max_results=max_results_per_query)
            except Exception as exc:  # noqa: BLE001
                print(f"Aviso: falha ao buscar por {query!r}: {exc}", file=sys.stderr)
                continue
            for result in results:
                url = result.get("href") or result.get("url")
                if not url or url in seen:
                    continue
                seen.add(url)
                candidates.append(Candidate(url=url, source_query=query, title=result.get("title", ""), snippet=result.get("body", "")))
            time.sleep(pause)
    return candidates


def discover_download_links(candidate: Candidate, timeout: int, max_links_per_page: int) -> list[Candidate]:
    if looks_like_pdf_url(candidate.url):
        return [candidate]
    response = request_get(candidate.url, timeout=timeout)
    if not response:
        return []
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" in content_type:
        return [candidate]
    if "text/html" not in content_type:
        return []
    try:
        html = response.content[:2_000_000].decode(response.encoding or "utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return []
    soup = BeautifulSoup(html, "html.parser")
    links: list[Candidate] = []
    seen: set[str] = set()
    for tag in soup.select("a[href]"):
        href = tag.get("href")
        if not href:
            continue
        absolute = dedupe_url(urljoin(candidate.url, href))
        if absolute in seen:
            continue
        anchor_text = tag.get_text(" ", strip=True)
        likely_pdf = looks_like_pdf_url(absolute) or contains_any(f"{anchor_text} {absolute}", ["pdf", "baixar", "download", "inteiro teor"])
        likely_petition = contains_any(
            f"{anchor_text} {absolute} {candidate.title} {candidate.snippet}",
            ["petição", "peticao", "inicial", "dano moral", "danos morais", "sentença", "sentenca"],
        )
        if likely_pdf and likely_petition:
            seen.add(absolute)
            links.append(Candidate(url=absolute, source_query=candidate.source_query, title=anchor_text or candidate.title, snippet=candidate.snippet))
        if len(links) >= max_links_per_page:
            break
    return links


def download_pdf_bytes(url: str, timeout: int) -> tuple[Optional[bytes], str]:
    response = request_get(url, timeout=timeout)
    if not response:
        return None, ""
    content_type = response.headers.get("content-type", "").lower()
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
        return None, content_type
    chunks = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_FILE_SIZE_BYTES:
                return None, content_type
            chunks.append(chunk)
    except requests.RequestException:
        return None, content_type
    data = b"".join(chunks)
    if not is_pdf_data(data, content_type):
        return None, content_type
    return data, content_type


def extract_text(file_path: Path, content_type: str) -> str:
    try:
        if file_path.suffix.lower() == ".pdf" or "pdf" in content_type:
            reader = PdfReader(str(file_path))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:30])
    except Exception:  # noqa: BLE001
        return ""
    return ""


def evaluate_document(text: str, title: str, snippet: str) -> tuple[bool, int, list[str]]:
    searchable = f"{title}\n{snippet}\n{text}"
    petition_matches = contains_any(searchable, PETITION_TERMS)
    favorable_matches = contains_any(text, FAVORABLE_TERMS)
    negative_matches = contains_any(text, NEGATIVE_TERMS)
    score = (len(petition_matches) * 2) + (len(favorable_matches) * 3) - (len(negative_matches) * 5)
    accepted = bool(petition_matches) and bool(favorable_matches) and not negative_matches and score >= 5
    return accepted, score, sorted(set(petition_matches + favorable_matches))


def load_existing_metadata(output_dir: Path) -> list[SavedDocument]:
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


def save_metadata(output_dir: Path, saved: list[SavedDocument]) -> None:
    json_path = output_dir / "metadata.json"
    csv_path = output_dir / "metadata.csv"
    json_path.write_text(json.dumps([asdict(item) for item in saved], ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=METADATA_FIELDS)
        writer.writeheader()
        for item in saved:
            row = asdict(item)
            row["matched_terms"] = "; ".join(item.matched_terms)
            writer.writerow(row)


def run() -> int:
    output_dir = DOWNLOADS_DIR.expanduser().resolve()
    accepted_dir = ACCEPTED_PDFS_DIR
    rejected_dir = REJECTED_PDFS_DIR
    accepted_dir.mkdir(parents=True, exist_ok=True)
    if KEEP_REJECTED:
        rejected_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + MAX_RUNTIME_SECONDS if MAX_RUNTIME_SECONDS else None
    existing_documents = load_existing_metadata(output_dir)
    saved = existing_documents.copy()
    existing_hashes = {item.sha256 for item in existing_documents if item.sha256}
    existing_urls = {dedupe_url(item.url) for item in existing_documents if item.url}
    print(f"Documentos já registrados: {len(existing_documents)}")
    print("Buscando candidatos na internet...")
    candidates = search_candidates(SEARCH_QUERIES, MAX_RESULTS, REQUEST_PAUSE, deadline)
    print(f"Encontrados {len(candidates)} resultados iniciais.")
    expanded: list[Candidate] = []
    seen_urls: set[str] = set(existing_urls)
    for candidate in tqdm(candidates, desc="Descobrindo links"):
        if deadline_reached(deadline):
            print("Tempo máximo de busca atingido durante a descoberta de links.")
            break
        for link in discover_download_links(candidate, HTTP_TIMEOUT, MAX_LINKS_PER_PAGE):
            deduped_link_url = dedupe_url(link.url)
            if deduped_link_url not in seen_urls:
                link.url = deduped_link_url
                expanded.append(link)
                seen_urls.add(deduped_link_url)
    print(f"Analisando {len(expanded)} possíveis PDFs novos...")
    new_saved_count = 0
    seen_hashes = set(existing_hashes)
    for candidate in tqdm(expanded, desc="Baixando e filtrando"):
        if deadline_reached(deadline):
            print("Tempo máximo de busca atingido durante os downloads.")
            break
        if new_saved_count >= DOWNLOAD_LIMIT:
            break
        data, content_type = download_pdf_bytes(candidate.url, timeout=HTTP_TIMEOUT)
        if not data:
            continue
        sha256 = hashlib.sha256(data).hexdigest()
        if sha256 in seen_hashes:
            continue
        seen_hashes.add(sha256)
        base_name = safe_file_name(candidate.title or Path(urlparse(candidate.url).path).stem or sha256[:12])
        temp_path = output_dir / f"tmp-{sha256[:12]}.pdf"
        temp_path.write_bytes(data)
        text = extract_text(temp_path, content_type)
        accepted, score, matched_terms = evaluate_document(text, candidate.title, candidate.snippet)
        if accepted:
            final_path = accepted_dir / f"{len(saved) + 1:03d}-{base_name}-{sha256[:8]}.pdf"
            temp_path.replace(final_path)
            saved.append(SavedDocument(final_path.name, candidate.url, candidate.source_query, candidate.title, score, matched_terms, sha256))
            new_saved_count += 1
        elif KEEP_REJECTED:
            temp_path.replace(rejected_dir / f"{base_name}-{sha256[:8]}.pdf")
        else:
            temp_path.unlink(missing_ok=True)
        time.sleep(REQUEST_PAUSE)
    save_metadata(output_dir, saved)
    print(f"Concluído. Novos PDFs aceitos: {new_saved_count}")
    print(f"Total de PDFs registrados: {len(saved)}")
    print(f"Arquivos salvos em: {accepted_dir}")
    print(f"Metadados: {output_dir / 'metadata.json'} e {output_dir / 'metadata.csv'}")
    print("Revise manualmente os documentos antes de usar. O filtro é heurístico.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
