"""Cálculo de benchmarks do corpus para comparação com a petição enviada."""

from __future__ import annotations

from collections import defaultdict

from src.domain.entities import DocumentSummary

BenchmarkMap = dict[str, dict[str, float]]


def compute_corpus_benchmarks(documents: list[DocumentSummary]) -> BenchmarkMap:
    """Calcula média, mediana e máximo de cada feature numérica do corpus."""
    numeric_features: dict[str, list[float]] = defaultdict(list)
    for doc in documents:
        for key, value in doc.features.items():
            if isinstance(value, bool):
                numeric_features[key].append(1.0 if value else 0.0)
            elif isinstance(value, (int, float)):
                numeric_features[key].append(float(value))

    benchmarks: BenchmarkMap = {}
    for key, values in numeric_features.items():
        if not values:
            continue
        sorted_values = sorted(values)
        median_index = len(sorted_values) // 2
        benchmarks[key] = {
            "media": round(sum(values) / len(values), 2),
            "mediana": round(sorted_values[median_index], 2),
            "max": round(max(values), 2),
        }
    return benchmarks
