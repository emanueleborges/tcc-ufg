"""Comparação humano × protótipo e relatório de validação."""

from __future__ import annotations

from src.domain.validation import (
    DIMENSION_LABELS,
    QUALITY_DIMENSIONS,
    ComparisonMetrics,
    HumanValidation,
    HumanValidationInput,
    ProblemAssessment,
)


def compute_comparison(
    prototype_scores: dict[str, float],
    human_scores: dict[str, float],
    assessments: list[ProblemAssessment],
) -> ComparisonMetrics:
    """Calcula MAE por dimensão e taxa de acordo nos problemas."""
    gaps: dict[str, float] = {}
    abs_errors: list[float] = []
    for name in QUALITY_DIMENSIONS:
        proto = float(prototype_scores.get(name, 0.0) or 0.0)
        human = float(human_scores.get(name, 0.0) or 0.0)
        gap = round(human - proto, 2)
        gaps[name] = gap
        abs_errors.append(abs(gap))

    mae = round(sum(abs_errors) / len(abs_errors), 2) if abs_errors else 0.0

    confirmed = sum(1 for a in assessments if a.verdict == "confirmed")
    partial = sum(1 for a in assessments if a.verdict == "partial")
    rejected = sum(1 for a in assessments if a.verdict == "rejected")
    total = len(assessments)
    if total:
        # confirmed=1, partial=0.5, rejected=0
        agreement = round((confirmed + 0.5 * partial) / total, 3)
    else:
        agreement = 1.0

    if mae <= 1.0 and agreement >= 0.75:
        summary = (
            "Alta aderência entre a análise do protótipo e a avaliação humana."
        )
    elif mae <= 2.5 and agreement >= 0.5:
        summary = (
            "Aderência moderada: há divergências pontuais que merecem revisão."
        )
    else:
        summary = (
            "Baixa aderência: recomenda-se revisar heurísticas/prompt e critérios."
        )

    return ComparisonMetrics(
        mae_scores=mae,
        agreement_rate=agreement,
        dimension_gaps=gaps,
        problems_confirmed=confirmed,
        problems_partial=partial,
        problems_rejected=rejected,
        summary=summary,
    )


def render_validation_markdown(validation: HumanValidation) -> str:
    """Gera relatório Markdown da validação humana."""
    lines = [
        "# Validação humana × protótipo",
        "",
        f"- **ID:** `{validation.validation_id}`",
        f"- **Petição:** {validation.petition_name or validation.petition_id}",
        f"- **Avaliador:** {validation.reviewer_name}",
        f"- **Data:** {validation.created_at}",
        f"- **Qualidade final (1–5):** {validation.final_quality}",
        "",
        "## Checklist do fluxograma",
        "",
        f"- Documentação produzida válida: {_yes(validation.documentation_ok)}",
        f"- Coesão textual: {_yes(validation.textual_cohesion_ok)}",
        f"- Consistência argumentativa: {_yes(validation.argumentative_consistency_ok)}",
        f"- Fundamentação jurídica: {_yes(validation.legal_basis_ok)}",
        "",
        "## Scores por dimensão",
        "",
        "| Dimensão | Protótipo | Humano | Δ |",
        "|---|---:|---:|---:|",
    ]
    for name in QUALITY_DIMENSIONS:
        label = DIMENSION_LABELS.get(name, name)
        proto = float(validation.prototype_scores.get(name, 0.0) or 0.0)
        human = float(validation.human_scores.get(name, 0.0) or 0.0)
        gap = validation.comparison.dimension_gaps.get(name, human - proto)
        lines.append(f"| {label} | {proto:.1f} | {human:.1f} | {gap:+.1f} |")

    cmp_ = validation.comparison
    lines.extend(
        [
            "",
            "## Comparação",
            "",
            f"- **MAE (scores):** {cmp_.mae_scores}",
            f"- **Taxa de acordo (problemas):** {cmp_.agreement_rate:.0%}",
            f"- Confirmados: {cmp_.problems_confirmed} · Parciais: {cmp_.problems_partial} · "
            f"Rejeitados: {cmp_.problems_rejected}",
            f"- **Síntese:** {cmp_.summary}",
            "",
            "## Problemas apontados pelo protótipo",
            "",
        ]
    )
    if not validation.problem_assessments:
        lines.append("- Nenhum problema listado para julgamento.")
    else:
        for item in validation.problem_assessments:
            note = f" — {item.note}" if item.note else ""
            lines.append(f"- [{item.verdict}] {item.problem}{note}")

    if validation.comments.strip():
        lines.extend(["", "## Comentários do avaliador", "", validation.comments.strip()])

    lines.append("")
    return "\n".join(lines)


def build_validation(
    validation_id: str,
    created_at: str,
    payload: HumanValidationInput,
) -> HumanValidation:
    comparison = compute_comparison(
        payload.prototype_scores,
        payload.human_scores,
        payload.problem_assessments,
    )
    draft = HumanValidation(
        validation_id=validation_id,
        petition_id=payload.petition_id,
        petition_name=payload.petition_name,
        reviewer_name=payload.reviewer_name,
        created_at=created_at,
        prototype_scores=dict(payload.prototype_scores),
        human_scores=dict(payload.human_scores),
        problem_assessments=list(payload.problem_assessments),
        documentation_ok=payload.documentation_ok,
        textual_cohesion_ok=payload.textual_cohesion_ok,
        argumentative_consistency_ok=payload.argumentative_consistency_ok,
        legal_basis_ok=payload.legal_basis_ok,
        final_quality=payload.final_quality,
        comments=payload.comments,
        comparison=comparison,
    )
    return HumanValidation(
        **{**draft.__dict__, "markdown_report": render_validation_markdown(draft)}
    )


def _yes(value: bool) -> str:
    return "sim" if value else "não"
