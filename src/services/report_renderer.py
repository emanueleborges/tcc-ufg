"""Renderização em markdown dos relatórios da aplicação."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from src.domain.entities import (
    Chunk,
    DocumentSummary,
    FeatureMap,
    Improvement,
    SimilarChunk,
    WebReference,
)
from src.infrastructure.nlp.text_utils import short_excerpt
from src.services.benchmarks import BenchmarkMap, compute_corpus_benchmarks

_DATE_FORMAT = "%d/%m/%Y %H:%M"
_TRECHO_LIMIT = 700


def render_review_markdown(
    petition_path: str,
    scores: dict[str, float],
    features: FeatureMap,
    benchmarks: BenchmarkMap,
    problems: list[str],
    suggestions: list[str],
    similar: list[SimilarChunk],
) -> str:
    """Markdown completo do relatório crítico da petição."""
    lines: list[str] = [
        "# Relatório de Crítica Jurídica Inteligente",
        "",
        f"Gerado em: {datetime.now().strftime(_DATE_FORMAT)}",
        f"Petição analisada: {petition_path}",
        "",
        "## Scores",
        "",
    ]
    for name, score in scores.items():
        lines.append(f"- {name.capitalize()}: {score}/10")

    lines.extend(["", "## Features extraídas", ""])
    for key, value in sorted(features.items()):
        if key in benchmarks:
            lines.append(
                f"- {key}: {value} | mediana da base: {benchmarks[key]['mediana']}"
            )
        else:
            lines.append(f"- {key}: {value}")

    lines.extend(["", "## Pontos fracos detectados", ""])
    lines.extend(
        [f"- {problem}" for problem in problems]
        or ["- Nenhum problema estrutural grave foi detectado pelas heurísticas iniciais."]
    )

    lines.extend(["", "## Sugestões de melhoria", ""])
    lines.extend(
        [f"- {suggestion}" for suggestion in suggestions]
        or ["- Nenhuma sugestão automática adicional foi gerada."]
    )

    lines.extend(["", "## Petições/trechos similares fortes", ""])
    for rank, item in enumerate(similar, start=1):
        excerpt = re.sub(r"\s+", " ", item.chunk.text[:_TRECHO_LIMIT]).strip()
        lines.extend(
            [
                f"### {rank}. Similaridade {item.score:.3f} — {item.chunk.file_name}",
                f"Seção detectada: {item.chunk.section}",
                "",
                f"> {excerpt}...",
                "",
            ]
        )

    lines.extend(
        [
            "## Prompt pronto para LLM crítico",
            "",
            "Analise a petição enviada comparando com os trechos similares fortes acima. "
            "Identifique argumentos ausentes, fragilidade jurídica, estrutura inferior, "
            "jurisprudência desatualizada, pedidos faltantes, falta de provas, clareza "
            "argumentativa e fundamentação superficial. Para cada problema, mostre "
            "trecho problemático, motivo, exemplo melhor e sugestão de reescrita.",
            "",
        ]
    )
    return "\n".join(lines)


def render_recreated_markdown(
    original_text: str,
    annotated_text: str,
    improvements: list[Improvement],
    unmatched: list[Improvement],
    web_references: list[WebReference],
    used_ollama: bool,
) -> str:
    """Markdown da petição recriada com comentários inline e resumo."""
    lines: list[str] = [
        "# Petição recriada com comentários",
        "",
        f"Gerada em: {datetime.now().strftime(_DATE_FORMAT)}",
        "",
        "> Esta é a sua petição original preservada na íntegra. As melhorias sugeridas "
        "aparecem entre colchetes no formato `[COMENTÁRIO (categoria): ...]` logo após "
        "o trecho ao qual se referem. Nenhuma palavra, fato, nome, data, valor ou "
        "pedido foi removido do texto original.",
        "",
        "## Petição original com comentários inline",
        "",
        annotated_text.strip(),
        "",
        "## Resumo das melhorias propostas",
        "",
    ]
    if improvements:
        for index, item in enumerate(improvements, start=1):
            lines.append(
                f"{index}. **{item.categoria.capitalize()}** — {item.comentario}"
            )
            lines.append(f"   Trecho: \"{short_excerpt(item.trecho, 200)}\"")
            lines.append("")
    else:
        lines.append("- Nenhuma melhoria foi proposta automaticamente. Reveja manualmente.")
        lines.append("")

    if unmatched:
        lines.append("### Comentários sem âncora exata no texto")
        lines.append("")
        for index, item in enumerate(unmatched, start=1):
            lines.append(
                f"{index}. **{item.categoria.capitalize()}** — {item.comentario}"
            )
            lines.append(
                f"   Trecho citado pelo modelo: \"{short_excerpt(item.trecho, 200)}\""
            )
            lines.append("")

    if web_references:
        lines.append("## Referências externas consultadas")
        lines.append("")
        for index, reference in enumerate(web_references, start=1):
            lines.append(f"{index}. {reference.title} — {reference.url}")
            if reference.snippet:
                lines.append(f"   {short_excerpt(reference.snippet, 240)}")
        lines.append("")

    if not used_ollama:
        lines.append(
            "> Aviso: a versão acima preserva apenas o texto original do PDF. "
            "Para gerar os comentários inline com sugestões de melhoria, ative o Ollama local."
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_corpus_report(
    documents: list[DocumentSummary],
    chunks: list[Chunk],
) -> str:
    """Markdown com estatísticas agregadas do corpus indexado."""
    benchmarks = compute_corpus_benchmarks(documents)
    section_counts = Counter(chunk.section for chunk in chunks)
    lines = [
        "# Relatório da Base RAG Jurídica",
        "",
        f"Gerado em: {datetime.now().strftime(_DATE_FORMAT)}",
        f"Documentos indexados: {len(documents)}",
        f"Chunks jurídicos: {len(chunks)}",
        "",
        "## Seções detectadas",
        "",
    ]
    for section, count in section_counts.most_common():
        lines.append(f"- {section}: {count}")

    lines.extend(["", "## Benchmarks da base", ""])
    for key, values in sorted(benchmarks.items()):
        lines.append(
            f"- {key}: média {values['media']} | mediana {values['mediana']} "
            f"| máximo {values['max']}"
        )

    lines.extend(
        [
            "",
            "## Próximo passo",
            "",
            "Execute `python app.py` para abrir a interface web e enviar uma petição em PDF.",
        ]
    )
    return "\n".join(lines)
