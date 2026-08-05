"""Cálculo dos scores da análise crítica da petição.

As dimensões seguem o fluxograma Intelligent.pdf:
estrutura, clareza, coerência, fundamentação, consistência e elementos essenciais.
"""

from __future__ import annotations

from src.domain.entities import DocumentSummary, FeatureMap
from src.domain.validation import QUALITY_DIMENSIONS
from src.services.benchmarks import BenchmarkMap, compute_corpus_benchmarks

_STRUCTURAL_FLAGS = ("tem_fatos", "tem_fundamentacao", "tem_pedidos")
_ESSENTIAL_FLAGS = (
    "tem_fatos",
    "tem_fundamentacao",
    "tem_pedidos",
    "valor_dano_moral",
    "pedidos_subsidiarios",
)
_RATIO_MULTIPLIER = 7.0
_MAX_SCORE = 10.0


def score_review(
    features: FeatureMap,
    documents: list[DocumentSummary],
) -> dict[str, float]:
    """Calcula pontuação multi-dimensional alinhada ao fluxograma."""
    benchmarks = compute_corpus_benchmarks(documents)
    fund = _ratio_score("artigos_legais", features, benchmarks)
    juris = _ratio_score("jurisprudencias", features, benchmarks)
    scores: dict[str, float] = {
        "estrutura": _structural_score(features),
        "clareza": _clarity_score(features),
        "coerencia": _coherence_score(features),
        "fundamentacao": round((fund + juris) / 2, 1),
        "consistencia": _consistency_score(features),
        "elementos_essenciais": _essentials_score(features, benchmarks),
    }
    # Mantém métricas auxiliares para o relatório detalhado.
    scores["jurisprudencia"] = juris
    scores["provas"] = _ratio_score("provas", features, benchmarks)
    scores["pedidos"] = 8.0 if features.get("tem_pedidos") else 3.0
    core = [scores[name] for name in QUALITY_DIMENSIONS]
    scores["geral"] = round(sum(core) / len(core), 1)
    return scores


def quality_scores_only(scores: dict[str, float]) -> dict[str, float]:
    """Extrai apenas as 6 dimensões do fluxograma (+ geral se existir)."""
    result = {name: float(scores.get(name, 0.0) or 0.0) for name in QUALITY_DIMENSIONS}
    if "geral" in scores:
        result["geral"] = float(scores["geral"])
    return result


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


def _coherence_score(features: FeatureMap) -> float:
    """Proxy de coerência: seções essenciais presentes e articuladas."""
    score = 3.0
    if features.get("tem_fatos"):
        score += 2.5
    if features.get("tem_fundamentacao"):
        score += 2.5
    if features.get("tem_pedidos"):
        score += 2.0
    # Penaliza narrativa sem pedido ou pedido sem fatos.
    if features.get("tem_pedidos") and not features.get("tem_fatos"):
        score -= 2.0
    if features.get("tem_fatos") and not features.get("tem_fundamentacao"):
        score -= 1.5
    return round(max(0.0, min(_MAX_SCORE, score)), 1)


def _consistency_score(features: FeatureMap) -> float:
    """Proxy de consistência: alinhamento fatos ↔ pedidos ↔ provas."""
    score = 5.0
    if features.get("tem_fatos") and features.get("tem_pedidos"):
        score += 2.0
    if int(features.get("provas", 0) or 0) > 0 and features.get("tem_fatos"):
        score += 1.5
    if features.get("valor_dano_moral") and features.get("tem_pedidos"):
        score += 1.5
    if features.get("tem_pedidos") and not features.get("tem_fatos"):
        score -= 3.0
    if features.get("valor_dano_moral") and not features.get("tem_pedidos"):
        score -= 2.0
    return round(max(0.0, min(_MAX_SCORE, score)), 1)


def _essentials_score(features: FeatureMap, benchmarks: BenchmarkMap) -> float:
    present = sum(bool(features.get(flag)) for flag in _ESSENTIAL_FLAGS)
    base = _MAX_SCORE * present / len(_ESSENTIAL_FLAGS)
    provas_median = float(benchmarks.get("provas", {}).get("mediana", 1) or 1)
    provas = float(features.get("provas", 0) or 0)
    if provas_median and provas >= provas_median:
        base = min(_MAX_SCORE, base + 1.0)
    return round(base, 1)
