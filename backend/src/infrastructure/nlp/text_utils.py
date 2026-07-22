"""Utilitários puros de manipulação textual."""

from __future__ import annotations

import re
from typing import Iterable

_CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_CNPJ_PATTERN = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_PROCESS_PATTERN = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_PATTERN = re.compile(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}")

_ACCENT_TRANSLATION = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
    "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
)


def normalize_text(text: str) -> str:
    """Normaliza espaços e quebras de linha mantendo a estrutura do texto."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def anonymize_text(text: str) -> str:
    """Substitui dados pessoais por marcadores genéricos."""
    text = _CPF_PATTERN.sub("[CPF]", text)
    text = _CNPJ_PATTERN.sub("[CNPJ]", text)
    text = _PROCESS_PATTERN.sub("[PROCESSO]", text)
    text = _EMAIL_PATTERN.sub("[EMAIL]", text)
    text = _PHONE_PATTERN.sub("[TELEFONE]", text)
    return text


def has_enough_text(text: str) -> bool:
    """Heurística: a página tem texto bruto extraível suficiente?"""
    return len(re.findall(r"\w+", text, flags=re.UNICODE)) >= 20


def fold_accents_preserving_length(text: str) -> str:
    """Remove acentos sem alterar o tamanho do texto (útil para ancoragem)."""
    return text.translate(_ACCENT_TRANSLATION)


def short_excerpt(text: str, limit: int = 1400) -> str:
    """Resumo curto de um texto, sem cortar palavras pela metade."""
    excerpt = re.sub(r"\s+", " ", text).strip()
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[:limit].rsplit(" ", 1)[0].strip() + "..."


def normalize_for_search(text: str) -> str:
    """Lowercase + remoção de acentos, usado em buscas e filtros."""
    return fold_accents_preserving_length(text).lower()


def contains_any(text: str, terms: Iterable[str]) -> list[str]:
    """Retorna a lista de ``terms`` encontrados em ``text`` (sem acento, case-insensitive)."""
    normalized = normalize_for_search(text)
    return [term for term in terms if normalize_for_search(term) in normalized]


def find_quote_span(haystack: str, needle: str) -> tuple[int, int] | None:
    """Localiza um trecho do LLM no texto original, tolerando acentos e espaços."""
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


def strip_markdown_inline(text: str) -> str:
    """Remove marcadores inline de markdown (`*`, `**`, `` ` ``) para conversão a PDF."""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def safe_file_name(text: str, default: str = "documento") -> str:
    """Converte um texto em nome de arquivo seguro (apenas a-z0-9._-)."""
    text = normalize_for_search(text or default)
    text = re.sub(r"[^a-z0-9._-]+", "-", text).strip("-._")
    return (text[:90] or default).strip("-")
