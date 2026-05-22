"""Extração de features jurídicas e estatísticas textuais de um trecho."""

from __future__ import annotations

import re

from src.domain.entities import FeatureMap
from src.domain.patterns import FEATURE_PATTERNS

_HAS_PEDIDOS_RE = re.compile(r"requer|pedido|condena[çc][ãa]o")
_HAS_FATOS_RE = re.compile(r"dos fatos|s[íi]ntese f[áa]tica|ocorreu|narr")
_HAS_FUND_RE = re.compile(r"do direito|fundamenta[çc][ãa]o|art\.?|jurisprud")


def extract_features(text: str) -> FeatureMap:
    """Extrai features quantitativas e booleanas de um trecho jurídico."""
    lowered = text.lower()
    features: FeatureMap = {}
    for name, pattern in FEATURE_PATTERNS.items():
        features[name] = len(re.findall(pattern, lowered, flags=re.IGNORECASE))

    words = re.findall(r"\w+", lowered, flags=re.UNICODE)
    sentences = re.split(r"[.!?]\s+", text)
    valid_sentences = [s for s in sentences if len(s.strip()) > 10]

    features["palavras"] = len(words)
    features["frases"] = len(valid_sentences)
    features["media_palavras_por_frase"] = round(
        len(words) / max(1, len(valid_sentences)), 2
    )
    features["tem_pedidos"] = bool(_HAS_PEDIDOS_RE.search(lowered))
    features["tem_fatos"] = bool(_HAS_FATOS_RE.search(lowered))
    features["tem_fundamentacao"] = bool(_HAS_FUND_RE.search(lowered))
    return features
