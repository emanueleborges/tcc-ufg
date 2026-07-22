"""Divisão de textos longos em chunks adequados para indexação."""

from __future__ import annotations

import re


def split_paragraph_chunks(
    text: str,
    *,
    max_chars: int,
    min_chars: int,
) -> list[str]:
    """Quebra ``text`` em chunks coesos, respeitando parágrafos.

    O algoritmo agrega parágrafos enquanto o limite ``max_chars`` não é
    atingido. Quando estoura, fecha o chunk atual (se grande o bastante)
    e começa um novo. Chunks com tamanho menor que ``min_chars`` são
    descartados ao final.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if len(current) >= min_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
            chunks.append(current[:max_chars])
            current = current[max_chars:]
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if len(chunk) >= min_chars]
