"""Detector heurístico de seção jurídica em um trecho de petição."""

from __future__ import annotations

import re

from src.domain.patterns import SECTION_PATTERNS

DEFAULT_SECTION = "geral"
_HEAD_WINDOW = 700


def detect_section(text: str) -> str:
    """Detecta a seção predominante de um trecho.

    Combina ocorrências no início do texto (peso maior) com a contagem
    global de cada padrão, escolhendo a seção com maior score.
    """
    lowered = text.lower()
    head = lowered[:_HEAD_WINDOW]
    scores: dict[str, int] = {}
    for section, patterns in SECTION_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, head, flags=re.IGNORECASE):
                score += 3
            score += len(re.findall(pattern, lowered, flags=re.IGNORECASE))
        if score:
            scores[section] = score
    if not scores:
        return DEFAULT_SECTION
    return max(scores.items(), key=lambda item: item[1])[0]
