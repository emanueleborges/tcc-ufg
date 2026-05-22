"""Inserção de comentários inline na petição original."""

from __future__ import annotations

from src.domain.entities import Improvement
from src.infrastructure.nlp.text_utils import find_quote_span


def insert_inline_comments(
    original_text: str,
    improvements: list[Improvement],
) -> tuple[str, list[Improvement]]:
    """Insere comentários após cada trecho referenciado.

    Retorna o texto anotado e a lista de melhorias que não puderam ser
    ancoradas (porque o trecho citado pelo LLM não foi encontrado).
    """
    insertions: list[tuple[int, str]] = []
    unmatched: list[Improvement] = []

    for item in improvements:
        span = find_quote_span(original_text, item.trecho)
        if span is None:
            unmatched.append(item)
            continue
        _, end = span
        line_end = original_text.find("\n", end)
        if line_end == -1:
            line_end = len(original_text)
        comment_line = f"\n\n[COMENTÁRIO ({item.categoria}): {item.comentario}]"
        insertions.append((line_end, comment_line))

    insertions.sort(key=lambda pair: pair[0], reverse=True)
    rebuilt = original_text
    for anchor, comment_line in insertions:
        rebuilt = rebuilt[:anchor] + comment_line + rebuilt[anchor:]
    return rebuilt, unmatched
