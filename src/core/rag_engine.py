#!/usr/bin/env python3
"""Motor de RAG e crítica jurídica.

Este arquivo contém apenas a lógica de leitura de PDF, chunking jurídico,
features, embeddings, busca semântica e geração de relatório.
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

try:
    from ddgs import DDGS
except ImportError:  # compatibilidade com versões antigas do pacote
    from duckduckgo_search import DDGS

from legal_config import (
    ACCEPTED_PDFS_DIR,
    ANONIMIZAR,
    EMBEDDING_MODEL,
    INDEX_DIR,
    MAX_CHUNK_CHARS,
    MIN_CHUNK_CHARS,
    REPORTS_DIR,
    TOP_K_SIMILARES,
)

SECTION_PATTERNS = {
    "cabecalho": [r"excelent[íi]ssim[ao]", r"ju[íi]z[ao]? de direito", r"vara (c[íi]vel|do trabalho|federal)"],
    "qualificacao": [r"qualifica[çc][ãa]o", r"brasileir[ao]", r"inscrit[ao] no cpf", r"pessoa jur[íi]dica"],
    "fatos": [r"dos fatos", r"s[íi]ntese f[áa]tica", r"da narrativa f[áa]tica", r"breve relato"],
    "fundamentacao": [r"do direito", r"dos fundamentos", r"fundamenta[çc][ãa]o jur[íi]dica", r"m[ée]rito"],
    "dano_moral": [r"do dano moral", r"danos morais", r"indeniza[çc][ãa]o por dano moral"],
    "jurisprudencia": [r"jurisprud[êe]ncia", r"precedentes", r"entendimento jurisprudencial", r"tribunal de justi[çc]a", r"superior tribunal de justi[çc]a", r"stj", r"stf"],
    "provas": [r"das provas", r"protesta provar", r"documentos anexos", r"prova documental"],
    "tutela": [r"tutela de urg[êe]ncia", r"tutela antecipada", r"liminar"],
    "pedidos": [r"dos pedidos", r"requer", r"requerimentos", r"ante o exposto"],
    "fechamento": [r"termos em que", r"pede deferimento", r"d[áa]-se [àa] causa"],
}

FEATURE_PATTERNS = {
    "artigos_legais": r"\b(art\.?|artigo)\s*\d+[\wº°-]*",
    "jurisprudencias": r"\b(stj|stf|tj[a-z]{2}|trf\d?|tst|recurso|apela[çc][ãa]o|agravo|ac[óo]rd[ãa]o)\b",
    "constitucional": r"constitui[çc][ãa]o|\bcf\b|art\.\s*5[º°]",
    "cdc": r"c[óo]digo de defesa do consumidor|\bcdc\b|consumidor",
    "codigo_civil": r"c[óo]digo civil|\bcc\b|responsabilidade civil|ato il[íi]cito",
    "provas": r"prova|documento|anexo|print|comprovante|testemunha|per[íi]cia",
    "pedidos_subsidiarios": r"subsidiariamente|sucessivamente|alternativamente",
    "valor_dano_moral": r"dano moral[^\n]{0,120}r\$|r\$[^\n]{0,120}dano moral",
    "tutela_urgencia": r"tutela de urg[êe]ncia|liminar|tutela antecipada",
    "gratuidade": r"gratuidade da justi[çc]a|justi[çc]a gratuita|hipossufici[êe]ncia",
}


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    file_name: str
    section: str
    text: str
    page_start: int
    page_end: int
    features: dict[str, int | bool | float]


@dataclass
class DocumentSummary:
    document_id: str
    file_name: str
    path: str
    chars: int
    chunks: int
    sections: dict[str, int]
    features: dict[str, int | bool | float]


@dataclass
class SimilarChunk:
    score: float
    chunk: Chunk


@dataclass
class ReviewResult:
    petition_path: str
    scores: dict[str, float]
    features: dict[str, int | bool | float]
    problems: list[str]
    suggestions: list[str]
    similar_chunks: list[SimilarChunk]
    markdown: str


@dataclass
class WebReference:
    title: str
    url: str
    snippet: str


@dataclass
class RecreatedPetition:
    markdown: str
    web_references: list[WebReference]
    used_ollama: bool
    warnings: list[str]


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def anonymize_text(text: str) -> str:
    text = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[CPF]", text)
    text = re.sub(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", "[CNPJ]", text)
    text = re.sub(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b", "[PROCESSO]", text)
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[EMAIL]", text)
    text = re.sub(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}", "[TELEFONE]", text)
    return text


def has_enough_text(text: str) -> bool:
    return len(re.findall(r"\w+", text, flags=re.UNICODE)) >= 20


@lru_cache(maxsize=1)
def get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_pdf_page(page) -> str:
    import fitz

    matrix = fitz.Matrix(2, 2)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
    result, _elapsed = get_ocr_engine()(image)
    if not result:
        return ""
    lines = [str(item[1]).strip() for item in result if len(item) >= 2 and str(item[1]).strip()]
    return normalize_text("\n".join(lines))


def ocr_pdf_pages(path: Path, native_pages: list[str]) -> list[str]:
    import fitz

    ocr_pages = native_pages.copy()
    with fitz.open(str(path)) as document:
        for index, page in enumerate(document):
            native_text = native_pages[index] if index < len(native_pages) else ""
            if has_enough_text(native_text):
                continue
            try:
                ocr_text = ocr_pdf_page(page)
            except Exception:  # noqa: BLE001
                ocr_text = ""
            if len(ocr_text) > len(native_text):
                ocr_pages[index] = ocr_text
    return ocr_pages


def read_pdf_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    native_pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    if all(has_enough_text(page_text) for page_text in native_pages):
        return native_pages
    return ocr_pdf_pages(path, native_pages)


def read_pdf_text(path: Path) -> str:
    return "\n\n".join(page for page in read_pdf_pages(path) if page.strip()).strip()


def detect_section(text: str) -> str:
    lowered = text.lower()
    head = lowered[:700]
    scores: dict[str, int] = {}
    for section, patterns in SECTION_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, head, flags=re.IGNORECASE):
                score += 3
            score += len(re.findall(pattern, lowered, flags=re.IGNORECASE))
        if score:
            scores[section] = score
    return max(scores.items(), key=lambda item: item[1])[0] if scores else "geral"


def split_paragraph_chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= MAX_CHUNK_CHARS:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if len(current) >= MIN_CHUNK_CHARS:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
            chunks.append(current[:MAX_CHUNK_CHARS])
            current = current[MAX_CHUNK_CHARS:]
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if len(chunk) >= MIN_CHUNK_CHARS]


def extract_features(text: str) -> dict[str, int | bool | float]:
    lowered = text.lower()
    features: dict[str, int | bool | float] = {}
    for name, pattern in FEATURE_PATTERNS.items():
        features[name] = len(re.findall(pattern, lowered, flags=re.IGNORECASE))
    words = re.findall(r"\w+", lowered, flags=re.UNICODE)
    sentences = re.split(r"[.!?]\s+", text)
    features["palavras"] = len(words)
    features["frases"] = len([s for s in sentences if len(s.strip()) > 10])
    features["media_palavras_por_frase"] = round(len(words) / max(1, int(features["frases"])), 2)
    features["tem_pedidos"] = bool(re.search(r"requer|pedido|condena[çc][ãa]o", lowered))
    features["tem_fatos"] = bool(re.search(r"dos fatos|s[íi]ntese f[áa]tica|ocorreu|narr", lowered))
    features["tem_fundamentacao"] = bool(re.search(r"do direito|fundamenta[çc][ãa]o|art\.?|jurisprud", lowered))
    return features


def build_chunks_for_pdf(path: Path) -> tuple[list[Chunk], DocumentSummary]:
    pages = read_pdf_pages(path)
    document_id = path.stem
    all_text = "\n\n".join(pages)
    if ANONIMIZAR:
        all_text = anonymize_text(all_text)
    raw_chunks = split_paragraph_chunks(all_text)
    chunks: list[Chunk] = []
    section_counter: Counter[str] = Counter()
    for index, chunk_text in enumerate(raw_chunks):
        section = detect_section(chunk_text)
        section_counter[section] += 1
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}:{index:04d}",
                document_id=document_id,
                file_name=path.name,
                section=section,
                text=chunk_text,
                page_start=1,
                page_end=len(pages),
                features=extract_features(chunk_text),
            )
        )
    summary = DocumentSummary(
        document_id=document_id,
        file_name=path.name,
        path=str(path),
        chars=len(all_text),
        chunks=len(chunks),
        sections=dict(section_counter),
        features=extract_features(all_text),
    )
    return chunks, summary


def embedding_prefix(texts: Iterable[str], kind: str) -> list[str]:
    prefix = "query: " if kind == "query" else "passage: "
    return [prefix + text.replace("\n", " ") for text in texts]


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vectors / norms


def build_index() -> tuple[list[Chunk], list[DocumentSummary], np.ndarray]:
    pdfs = sorted(ACCEPTED_PDFS_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Nenhum PDF encontrado em {ACCEPTED_PDFS_DIR}. Rode webscrap.py primeiro.")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    all_chunks: list[Chunk] = []
    documents: list[DocumentSummary] = []
    # Detecta se está rodando no Streamlit
    is_streamlit = "streamlit" in sys.modules
    for path in tqdm(pdfs, desc="Extraindo PDFs", disable=is_streamlit):
        try:
            chunks, summary = build_chunks_for_pdf(path)
        except Exception as exc:  # noqa: BLE001
            print(f"Aviso: falha ao processar {path.name}: {exc}")
            continue
        if chunks:
            all_chunks.extend(chunks)
            documents.append(summary)
    if not all_chunks:
        raise SystemExit("Nenhum texto útil foi extraído dos PDFs.")
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = embedding_prefix((chunk.text for chunk in all_chunks), "passage")
    embeddings = model.encode(texts, batch_size=16, show_progress_bar=not is_streamlit, convert_to_numpy=True)
    embeddings = normalize_vectors(embeddings.astype("float32"))
    with (INDEX_DIR / "chunks.jsonl").open("w", encoding="utf-8") as file:
        for chunk in all_chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    (INDEX_DIR / "documentos.json").write_text(
        json.dumps([asdict(doc) for doc in documents], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    np.save(INDEX_DIR / "embeddings.npy", embeddings)
    return all_chunks, documents, embeddings


def load_index() -> tuple[list[Chunk], list[DocumentSummary], np.ndarray]:
    chunks_path = INDEX_DIR / "chunks.jsonl"
    documents_path = INDEX_DIR / "documentos.json"
    embeddings_path = INDEX_DIR / "embeddings.npy"
    if not chunks_path.exists() or not documents_path.exists() or not embeddings_path.exists():
        return build_index()
    chunks = []
    with chunks_path.open("r", encoding="utf-8") as file:
        for line in file:
            chunks.append(Chunk(**json.loads(line)))
    documents = [DocumentSummary(**row) for row in json.loads(documents_path.read_text(encoding="utf-8"))]
    embeddings = np.load(embeddings_path)
    return chunks, documents, embeddings


def search_similar(query_text: str, chunks: list[Chunk], embeddings: np.ndarray, top_k: int, exclude_document_id: str | None = None) -> list[SimilarChunk]:
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_vector = model.encode(embedding_prefix([query_text], "query"), convert_to_numpy=True).astype("float32")
    query_vector = normalize_vectors(query_vector)
    scores = np.dot(embeddings.astype("float64"), query_vector[0].astype("float64"))
    ordered_indices = np.argsort(scores)[::-1]
    similar: list[SimilarChunk] = []
    for index in ordered_indices:
        if exclude_document_id and chunks[index].document_id == exclude_document_id:
            continue
        similar.append(SimilarChunk(score=float(scores[index]), chunk=chunks[index]))
        if len(similar) >= top_k:
            break
    return similar


def corpus_benchmarks(documents: list[DocumentSummary]) -> dict[str, dict[str, float]]:
    numeric_features: dict[str, list[float]] = defaultdict(list)
    for doc in documents:
        for key, value in doc.features.items():
            if isinstance(value, bool):
                numeric_features[key].append(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                numeric_features[key].append(float(value))
    benchmarks = {}
    for key, values in numeric_features.items():
        sorted_values = sorted(values)
        benchmarks[key] = {"media": round(sum(values) / len(values), 2), "mediana": round(sorted_values[len(sorted_values) // 2], 2), "max": round(max(values), 2)}
    return benchmarks


def score_review(features: dict[str, int | bool | float], documents: list[DocumentSummary]) -> dict[str, float]:
    refs = corpus_benchmarks(documents)
    def ratio(name: str) -> float:
        value = float(features.get(name, 0) or 0)
        median = float(refs.get(name, {}).get("mediana", 1) or 1)
        return min(10.0, round((value / median) * 7.0, 1)) if median else 0.0
    scores = {
        "estrutura": 0.0,
        "fundamentacao": ratio("artigos_legais"),
        "jurisprudencia": ratio("jurisprudencias"),
        "provas": ratio("provas"),
        "pedidos": 8.0 if features.get("tem_pedidos") else 3.0,
        "clareza": 0.0,
    }
    structural_flags = ["tem_fatos", "tem_fundamentacao", "tem_pedidos"]
    scores["estrutura"] = round(10 * sum(bool(features.get(flag)) for flag in structural_flags) / len(structural_flags), 1)
    avg_words = float(features.get("media_palavras_por_frase", 0) or 0)
    scores["clareza"] = 8.0 if 12 <= avg_words <= 35 else 6.0 if avg_words <= 45 else 4.0
    scores["geral"] = round(sum(scores.values()) / len(scores), 1)
    return scores


def analyze_petition(petition_path: Path, chunks: list[Chunk], documents: list[DocumentSummary], embeddings: np.ndarray) -> ReviewResult:
    petition_chunks, petition_summary = build_chunks_for_pdf(petition_path)
    full_text = "\n\n".join(chunk.text for chunk in petition_chunks)
    features = petition_summary.features
    scores = score_review(features, documents)
    benchmarks = corpus_benchmarks(documents)
    similar = search_similar(full_text[:6000], chunks, embeddings, TOP_K_SIMILARES, exclude_document_id=petition_summary.document_id)
    problems: list[str] = []
    suggestions: list[str] = []
    if not features.get("tem_fatos"):
        problems.append("A narrativa dos fatos não foi identificada com clareza.")
        suggestions.append("Crie uma seção objetiva de fatos, em ordem cronológica, conectando cada fato ao dano sofrido.")
    if not features.get("tem_fundamentacao"):
        problems.append("A fundamentação jurídica parece superficial ou pouco sinalizada.")
        suggestions.append("Inclua base legal expressa, responsabilidade civil, nexo causal, dano e culpa/risco, conforme o caso.")
    if not features.get("tem_pedidos"):
        problems.append("Os pedidos não foram identificados de forma robusta.")
        suggestions.append("Separe pedidos em itens numerados, incluindo citação, procedência, condenação, juros, correção, custas e honorários.")
    if int(features.get("jurisprudencias", 0) or 0) < float(benchmarks.get("jurisprudencias", {}).get("mediana", 1)):
        problems.append("A quantidade de jurisprudência está abaixo da mediana das petições de referência.")
        suggestions.append("Inclua precedentes recentes e conecte cada precedente ao ponto jurídico discutido.")
    if int(features.get("provas", 0) or 0) < float(benchmarks.get("provas", {}).get("mediana", 1)):
        problems.append("A menção a provas/documentos está abaixo do padrão do corpus.")
        suggestions.append("Explique quais documentos provam cada fato: prints, contratos, protocolos, laudos, comprovantes e testemunhas.")
    if not features.get("pedidos_subsidiarios"):
        suggestions.append("Avalie incluir pedidos subsidiários ou sucessivos para aumentar a resiliência da tese.")
    if not features.get("valor_dano_moral"):
        suggestions.append("Indique valor pretendido para dano moral e justifique proporcionalidade, razoabilidade e caráter pedagógico.")
    markdown = render_review_markdown(str(petition_path), scores, features, benchmarks, problems, suggestions, similar)
    return ReviewResult(str(petition_path), scores, features, problems, suggestions, similar, markdown)


def render_review_markdown(petition_path: str, scores: dict[str, float], features: dict[str, int | bool | float], benchmarks: dict[str, dict[str, float]], problems: list[str], suggestions: list[str], similar: list[SimilarChunk]) -> str:
    lines = ["# Relatório de Crítica Jurídica Inteligente", "", f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", f"Petição analisada: {petition_path}", "", "## Scores", ""]
    for name, score in scores.items():
        lines.append(f"- {name.capitalize()}: {score}/10")
    lines.extend(["", "## Features extraídas", ""])
    for key, value in sorted(features.items()):
        if key in benchmarks:
            lines.append(f"- {key}: {value} | mediana da base: {benchmarks[key]['mediana']}")
        else:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Pontos fracos detectados", ""])
    lines.extend([f"- {problem}" for problem in problems] or ["- Nenhum problema estrutural grave foi detectado pelas heurísticas iniciais."])
    lines.extend(["", "## Sugestões de melhoria", ""])
    lines.extend([f"- {suggestion}" for suggestion in suggestions] or ["- Nenhuma sugestão automática adicional foi gerada."])
    lines.extend(["", "## Petições/trechos similares fortes", ""])
    for rank, item in enumerate(similar, start=1):
        excerpt = re.sub(r"\s+", " ", item.chunk.text[:700]).strip()
        lines.extend([f"### {rank}. Similaridade {item.score:.3f} — {item.chunk.file_name}", f"Seção detectada: {item.chunk.section}", "", f"> {excerpt}...", ""])
    lines.extend(["## Prompt pronto para LLM crítico", "", "Analise a petição enviada comparando com os trechos similares fortes acima. Identifique argumentos ausentes, fragilidade jurídica, estrutura inferior, jurisprudência desatualizada, pedidos faltantes, falta de provas, clareza argumentativa e fundamentação superficial. Para cada problema, mostre trecho problemático, motivo, exemplo melhor e sugestão de reescrita.", ""])
    return "\n".join(lines)


def short_excerpt(text: str, limit: int = 1400) -> str:
    excerpt = re.sub(r"\s+", " ", text).strip()
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[:limit].rsplit(" ", 1)[0].strip() + "..."


def search_web_references(review: ReviewResult, max_results: int = 5) -> list[WebReference]:
    query_terms = [
        "petição inicial dano moral responsabilidade civil jurisprudência recente",
        "indenização por dano moral petição inicial fundamentos pedidos provas",
    ]
    if review.problems:
        query_terms.append(f"petição inicial {' '.join(review.problems[:2])} jurisprudência")
    references: list[WebReference] = []
    seen_urls: set[str] = set()
    with DDGS() as ddgs:
        for query in query_terms:
            if len(references) >= max_results:
                break
            try:
                results = ddgs.text(query, region="br-pt", safesearch="moderate", max_results=max_results)
            except Exception:  # noqa: BLE001
                continue
            for result in results:
                url = result.get("href") or result.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                references.append(
                    WebReference(
                        title=str(result.get("title", "")).strip(),
                        url=url,
                        snippet=str(result.get("body", "")).strip(),
                    )
                )
                if len(references) >= max_results:
                    break
    return references


def render_web_references(web_references: list[WebReference]) -> str:
    if not web_references:
        return "Nenhuma referência externa foi encontrada."
    lines = []
    for index, reference in enumerate(web_references, start=1):
        lines.append(f"{index}. {reference.title}\nURL: {reference.url}\nResumo: {reference.snippet}")
    return "\n\n".join(lines)


def request_ollama(prompt: str, model: str, timeout: int = 240, options: dict | None = None) -> str:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if options:
        payload["options"] = options
    response = requests.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    text = str(data.get("response", "")).strip()
    if not text:
        raise RuntimeError("O Ollama respondeu sem texto.")
    return text


def extract_json_block(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def generate_improvements_with_ollama(
    original_text: str,
    review: ReviewResult,
    web_references: list[WebReference],
    model: str,
) -> list[dict]:
    rag_context = "\n\n".join(
        f"- {item.chunk.section} | {item.chunk.file_name}: {short_excerpt(item.chunk.text, 700)}"
        for item in review.similar_chunks[:5]
    )
    problems = "\n".join(f"- {item}" for item in review.problems) or "- Sem pontos críticos automáticos."
    suggestions = "\n".join(f"- {item}" for item in review.suggestions) or "- Reorganizar e fortalecer a estrutura."
    references_block = render_web_references(web_references)
    petition_excerpt = short_excerpt(original_text, 12000)
    prompt = f"""
Você é um assistente jurídico brasileiro. Sua tarefa é apontar melhorias concretas em uma petição já existente, SEM reescrevê-la.

Responda SOMENTE com JSON válido, sem nenhum texto antes ou depois, no formato:
{{
  "melhorias": [
    {{
      "trecho": "trecho curto copiado literalmente da petição (15 a 40 palavras)",
      "comentario": "explicação objetiva da melhoria (1 a 3 frases)",
      "categoria": "fatos|fundamentacao|jurisprudencia|provas|pedidos|estrutura|clareza"
    }}
  ],
  "resumo": "frase curta resumindo o conjunto das melhorias propostas"
}}

Regras rígidas:
- NÃO reescreva a petição. NÃO retorne a petição inteira. Retorne apenas o JSON descrito.
- Cada item de "melhorias" deve apontar uma melhoria real e específica.
- "trecho" deve ser copiado IPSIS LITTERIS de dentro da petição abaixo (não invente nem parafraseie).
- Não invente fatos, datas, valores, jurisprudência, número de processo ou nome.
- Use a base RAG e as referências externas apenas como apoio para sugerir melhorias jurídicas válidas.
- Liste no mínimo 3 e no máximo 8 melhorias.
- Se a petição já estiver muito boa em algum ponto, ainda assim aponte melhorias acessórias (clareza, organização, anexos, jurisprudência atualizada genérica).

Pontos fracos detectados pela análise automática:
{problems}

Sugestões da análise automática:
{suggestions}

Base RAG (apoio para fundamentação genérica):
{rag_context}

Referências externas (apenas para inspirar sugestões; não copie textualmente):
{references_block}

Petição original (use apenas como fonte para os trechos literais):
\"\"\"
{petition_excerpt}
\"\"\"
""".strip()
    raw = request_ollama(prompt, model, options={"temperature": 0.2, "num_ctx": 8192})
    json_text = extract_json_block(raw)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"O Ollama não retornou JSON válido: {exc}. Resposta: {raw[:400]}") from exc
    melhorias = data.get("melhorias", [])
    cleaned: list[dict] = []
    for item in melhorias:
        if not isinstance(item, dict):
            continue
        trecho = str(item.get("trecho", "")).strip()
        comentario = str(item.get("comentario", "")).strip()
        categoria = str(item.get("categoria", "geral")).strip() or "geral"
        if not trecho or not comentario:
            continue
        cleaned.append({"trecho": trecho, "comentario": comentario, "categoria": categoria})
    return cleaned


def fold_accents_preserving_length(text: str) -> str:
    replacements = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
    )
    return text.translate(replacements)


def find_quote_span(haystack: str, needle: str) -> tuple[int, int] | None:
    if not needle.strip():
        return None
    folded_haystack = fold_accents_preserving_length(haystack).lower()
    folded_needle = fold_accents_preserving_length(needle).lower()
    words = [word for word in re.findall(r"\w+", folded_needle) if word]
    if not words:
        return None
    for window in (12, 8, 5, 3):
        size = min(window, len(words))
        if size < 3:
            continue
        pattern = r"\W+".join(re.escape(word) for word in words[:size])
        match = re.search(pattern, folded_haystack)
        if match:
            return match.start(), match.end()
    return None


def insert_inline_comments(original_text: str, improvements: list[dict]) -> tuple[str, list[dict]]:
    insertions: list[tuple[int, str, dict]] = []
    unmatched: list[dict] = []
    for item in improvements:
        span = find_quote_span(original_text, item["trecho"])
        if span is None:
            unmatched.append(item)
            continue
        _, end = span
        line_end = original_text.find("\n", end)
        if line_end == -1:
            line_end = len(original_text)
        anchor = line_end
        comment_line = f"\n\n[COMENTÁRIO ({item['categoria']}): {item['comentario']}]"
        insertions.append((anchor, comment_line, item))
    insertions.sort(key=lambda pair: pair[0], reverse=True)
    rebuilt = original_text
    for anchor, comment_line, _item in insertions:
        rebuilt = rebuilt[:anchor] + comment_line + rebuilt[anchor:]
    return rebuilt, unmatched


def render_recreated_markdown(
    original_text: str,
    annotated_text: str,
    improvements: list[dict],
    unmatched: list[dict],
    web_references: list[WebReference],
    used_ollama: bool,
) -> str:
    lines = [
        "# Petição recriada com comentários",
        "",
        f"Gerada em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "> Esta é a sua petição original preservada na íntegra. As melhorias sugeridas aparecem entre colchetes "
        "no formato `[COMENTÁRIO (categoria): ...]` logo após o trecho ao qual se referem. "
        "Nenhuma palavra, fato, nome, data, valor ou pedido foi removido do texto original.",
        "",
        "## Petição original com comentários inline",
        "",
        annotated_text.strip(),
        "",
        "## Resumo das melhorias propostas",
        "",
    ]
    if improvements:
        for index, item in enumerate(improvements, start=1):
            lines.append(f"{index}. **{item['categoria'].capitalize()}** — {item['comentario']}")
            lines.append(f"   Trecho: \"{short_excerpt(item['trecho'], 200)}\"")
            lines.append("")
    else:
        lines.append("- Nenhuma melhoria foi proposta automaticamente. Reveja manualmente.")
        lines.append("")
    if unmatched:
        lines.append("### Comentários sem âncora exata no texto")
        lines.append("")
        for index, item in enumerate(unmatched, start=1):
            lines.append(f"{index}. **{item['categoria'].capitalize()}** — {item['comentario']}")
            lines.append(f"   Trecho citado pelo modelo: \"{short_excerpt(item['trecho'], 200)}\"")
            lines.append("")
    if web_references:
        lines.append("## Referências externas consultadas")
        lines.append("")
        for index, reference in enumerate(web_references, start=1):
            lines.append(f"{index}. {reference.title} — {reference.url}")
            if reference.snippet:
                lines.append(f"   {short_excerpt(reference.snippet, 240)}")
        lines.append("")
    if not used_ollama:
        lines.append("> Aviso: a versão acima preserva apenas o texto original do PDF. Para gerar os comentários "
                     "inline com sugestões de melhoria, ative o Ollama local.")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_recreated_petition(
    petition_path: Path,
    review: ReviewResult,
    use_internet: bool = False,
    use_ollama: bool = False,
    ollama_model: str = "llama3:latest",
) -> RecreatedPetition:
    original_text = read_pdf_text(petition_path)
    web_references = search_web_references(review) if use_internet else []
    warnings: list[str] = []
    if not original_text:
        warnings.append("Não foi possível extrair texto útil do PDF. A recriação integral depende de um PDF com texto selecionável ou OCR funcional.")
        original_text = "[Não foi possível extrair o texto integral da petição enviada.]"

    improvements: list[dict] = []
    unmatched: list[dict] = []
    annotated_text = original_text
    used_ollama = False
    if use_ollama:
        try:
            improvements = generate_improvements_with_ollama(original_text, review, web_references, ollama_model)
            used_ollama = True
            if improvements:
                annotated_text, unmatched = insert_inline_comments(original_text, improvements)
            else:
                warnings.append("O Ollama não retornou melhorias. Mantida a petição original sem comentários.")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Ollama indisponível ou falhou: {exc}. Mantida a petição original sem comentários automáticos.")
    else:
        warnings.append("Ollama não foi usado. A saída preserva a petição original extraída do PDF, sem comentários automáticos.")

    markdown = render_recreated_markdown(
        original_text=original_text,
        annotated_text=annotated_text,
        improvements=improvements,
        unmatched=unmatched,
        web_references=web_references,
        used_ollama=used_ollama,
    )
    return RecreatedPetition(markdown, web_references, used_ollama, warnings)


def strip_markdown_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def markdown_to_pdf(markdown: str, output_path: Path) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("Instale a dependência reportlab para gerar PDF: pip install reportlab") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 8))
            continue
        style = styles["BodyText"]
        if line.startswith("# "):
            style = styles["Title"]
            line = line[2:].strip()
        elif line.startswith("## "):
            style = styles["Heading2"]
            line = line[3:].strip()
        elif line.startswith("### "):
            style = styles["Heading3"]
            line = line[4:].strip()
        elif line.startswith("#### "):
            style = styles["Heading4"]
            line = line[5:].strip()
        elif re.match(r"^[-*]\s+", line):
            line = "• " + re.sub(r"^[-*]\s+", "", line)
        elif line.startswith(">"):
            line = line.lstrip("> ").strip()
        line = strip_markdown_inline(line)
        wrapped = "<br/>".join(escape(part) for part in textwrap.wrap(line, width=105) or [""])
        story.append(Paragraph(wrapped, style))
    document.build(story)
    return output_path


def make_critic_report(petition_path: Path, chunks: list[Chunk], documents: list[DocumentSummary], embeddings: np.ndarray) -> Path:
    result = analyze_petition(petition_path, chunks, documents, embeddings)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "relatorio_critico.md"
    report_path.write_text(result.markdown, encoding="utf-8")
    return report_path


def write_corpus_report(documents: list[DocumentSummary], chunks: list[Chunk]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "relatorio_base_rag.md"
    benchmarks = corpus_benchmarks(documents)
    section_counts = Counter(chunk.section for chunk in chunks)
    lines = ["# Relatório da Base RAG Jurídica", "", f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", f"Documentos indexados: {len(documents)}", f"Chunks jurídicos: {len(chunks)}", "", "## Seções detectadas", ""]
    for section, count in section_counts.most_common():
        lines.append(f"- {section}: {count}")
    lines.extend(["", "## Benchmarks da base", ""])
    for key, values in sorted(benchmarks.items()):
        lines.append(f"- {key}: média {values['media']} | mediana {values['mediana']} | máximo {values['max']}")
    lines.extend(["", "## Próximo passo", "", "Abra a interface com `streamlit run interface.py` e envie uma petição em PDF para análise."])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
