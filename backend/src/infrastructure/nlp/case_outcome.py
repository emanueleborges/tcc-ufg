"""Classificação do resultado processual e metadados de caso para o RAG."""

from __future__ import annotations

import re
from typing import Literal

from src.domain.entities import FeatureMap
from src.domain.patterns import FAVORABLE_TERMS, NEGATIVE_TERMS
from src.infrastructure.nlp.text_utils import contains_any

CaseOutcome = Literal["deferido", "indeferido", "parcial", "indefinido"]

_ACTION_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("indenizacao_dano_moral", re.compile(r"indeniza[çc][ãa]o.{0,40}dano moral|dano moral", re.I)),
    ("obrigacao_fazer", re.compile(r"obriga[çc][ãa]o de fazer", re.I)),
    ("revisional", re.compile(r"a[çc][ãa]o revisional|revis[ãa]o de contrato", re.I)),
    ("cobranca", re.compile(r"a[çc][ãa]o de cobran[çc]a", re.I)),
    ("trabalhista", re.compile(r"reclama[çc][ãa]o trabalhista|justa causa|fgts", re.I)),
]

_SUBJECT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("consumo", re.compile(r"consumidor|c[óo]digo de defesa|\bcdc\b", re.I)),
    ("responsabilidade_civil", re.compile(r"responsabilidade civil|ato il[íi]cito", re.I)),
    ("bancario", re.compile(r"banco|cart[ãa]o de cr[ée]dito|conta corrente", re.I)),
    ("saude", re.compile(r"plano de sa[úu]de|negativa de cobertura", re.I)),
    ("transporte", re.compile(r"companhia a[ée]rea|atraso de voo|overbooking", re.I)),
]

_PARTIAL_TERMS = (
    "julgo parcialmente procedente",
    "parcialmente procedente",
    "provimento parcial",
    "procedência parcial",
    "procedencia parcial",
)


def classify_outcome(text: str) -> CaseOutcome:
    """Infere se o documento aponta deferimento, indeferimento ou parcial."""
    lowered = text.lower()
    partial = any(term in lowered for term in _PARTIAL_TERMS)
    favorable = contains_any(text, FAVORABLE_TERMS)
    negative = contains_any(text, NEGATIVE_TERMS)

    if partial and not negative:
        return "parcial"
    if favorable and negative:
        # Conflito textual: prioriza menção mais forte no dispositivo final.
        tail = lowered[-4000:]
        if any(term in tail for term in _PARTIAL_TERMS):
            return "parcial"
        if contains_any(tail, NEGATIVE_TERMS) and not contains_any(tail, FAVORABLE_TERMS):
            return "indeferido"
        if contains_any(tail, FAVORABLE_TERMS):
            return "deferido"
        return "parcial"
    if favorable:
        return "deferido"
    if negative:
        return "indeferido"
    return "indefinido"


def detect_action_type(text: str) -> str:
    for label, pattern in _ACTION_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return "geral"


def detect_subjects(text: str) -> list[str]:
    return [label for label, pattern in _SUBJECT_PATTERNS if pattern.search(text)]


def enrich_case_features(text: str, features: FeatureMap | None = None) -> FeatureMap:
    """Acrescenta metadados de resultado/assunto às features do documento/chunk."""
    enriched: FeatureMap = dict(features or {})
    outcome = classify_outcome(text)
    subjects = detect_subjects(text)
    enriched["resultado"] = outcome
    enriched["resultado_deferido"] = outcome == "deferido"
    enriched["resultado_indeferido"] = outcome == "indeferido"
    enriched["resultado_parcial"] = outcome == "parcial"
    enriched["tipo_acao"] = detect_action_type(text)
    enriched["assuntos"] = ", ".join(subjects) if subjects else "nao_classificado"
    enriched["tem_decisao"] = outcome != "indefinido"
    return enriched


def outcome_label(outcome: str) -> str:
    return {
        "deferido": "deferido (procedente / provido)",
        "indeferido": "indeferido (improcedente / negado)",
        "parcial": "parcialmente deferido",
        "indefinido": "resultado não identificado",
    }.get(outcome, outcome)
