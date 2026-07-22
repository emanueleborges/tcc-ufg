"""Cálculo dos scores da análise crítica da petição."""

from __future__ import annotations

from src.domain.entities import DocumentSummary, FeatureMap
from src.services.benchmarks import BenchmarkMap, compute_corpus_benchmarks

_STRUCTURAL_FLAGS = ("tem_fatos", "tem_fundamentacao", "tem_pedidos")
_RATIO_MULTIPLIER = 7.0
_MAX_SCORE = 10.0


def score_review(
    features: FeatureMap,
    documents: list[DocumentSummary],
) -> dict[str, float]:
    """Calcula uma pontuação multi-dimensional comparando com o corpus."""
    benchmarks = compute_corpus_benchmarks(documents)
    scores: dict[str, float] = {
        "estrutura": _structural_score(features),
        "fundamentacao": _ratio_score("artigos_legais", features, benchmarks),
        "jurisprudencia": _ratio_score("jurisprudencias", features, benchmarks),
        "provas": _ratio_score("provas", features, benchmarks),
        "pedidos": 8.0 if features.get("tem_pedidos") else 3.0,
        "clareza": _clarity_score(features),
    }
    scores["geral"] = round(sum(scores.values()) / len(scores), 1)
    return scores


def _ratio_score(
    name: str,
    features: FeatureMap,
    benchmarks: BenchmarkMap,
) -> float:
    value = float(features.get(name, 0) or 0)
    median = float(benchmarks.get(name, {}).get("mediana", 1) or 1)
    if not median:
        return 0.0
    return min(_MAX_SCORE, round((value / median) * _RATIO_MULTIPLIER, 1))


def _structural_score(features: FeatureMap) -> float:
    present = sum(bool(features.get(flag)) for flag in _STRUCTURAL_FLAGS)
    return round(_MAX_SCORE * present / len(_STRUCTURAL_FLAGS), 1)


def _clarity_score(features: FeatureMap) -> float:
    avg_words = float(features.get("media_palavras_por_frase", 0) or 0)
    if 12 <= avg_words <= 35:
        return 8.0
    if avg_words <= 45:
        return 6.0
    return 4.0
