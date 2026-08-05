"""Gera PDF recriado preservando a estrutura visual do PDF original.

Copia as páginas da petição original e acrescenta:
- destaque (highlight) nos trechos referidos;
- anotações de texto com o comentário de melhoria;
- página final de resumo (melhorias sem âncora / lista).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.domain.entities import Improvement

# Destaque azul dos trechos modificados / comentados no PDF original.
_BLUE_HIGHLIGHT = (0.20, 0.45, 0.95)
_BLUE_ANNOT = (0.10, 0.35, 0.85)
_BLUE_FILL = (0.90, 0.94, 1.0)


def rebuild_annotated_petition_pdf(
    *,
    original_pdf: Path,
    output_pdf: Path,
    improvements: list[Improvement],
    unmatched: list[Improvement],
) -> Path:
    """Salva um PDF com o layout original + comentários ancorados."""
    import fitz

    if not original_pdf.is_file():
        raise FileNotFoundError(f"PDF original não encontrado: {original_pdf}")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(str(original_pdf))
    anchored = 0

    try:
        for item in improvements:
            if _annotate_improvement(document, item):
                anchored += 1

        _append_summary_page(
            document,
            improvements=improvements,
            unmatched=unmatched,
            anchored_count=anchored,
        )
        document.save(str(output_pdf), garbage=4, deflate=True)
    finally:
        document.close()

    return output_pdf


def _annotate_improvement(document, item: Improvement) -> bool:
    import fitz

    quote = (item.trecho or "").strip()
    if len(quote) < 8:
        return False

    candidates = _quote_candidates(quote)
    for page in document:
        for candidate in candidates:
            hits = page.search_for(candidate)
            if not hits:
                # busca case-insensitive aproximada via flags quando disponível
                try:
                    hits = page.search_for(candidate, flags=fitz.TEXT_DEHYPHENATE)
                except TypeError:
                    hits = []
            if not hits:
                continue

            rect = hits[0]
            try:
                highlight = page.add_highlight_annot(rect)
                highlight.set_colors(stroke=_BLUE_HIGHLIGHT)
                highlight.set_opacity(0.45)
                highlight.update()
            except Exception:  # noqa: BLE001
                pass

            comment = f"[{item.categoria}] {item.comentario}".strip()
            comment = comment[:900]
            try:
                point = fitz.Point(min(rect.x1 + 2, page.rect.width - 18), max(rect.y0, 18))
                annot = page.add_text_annot(point, comment)
                annot.set_info(title="Crítico Jurídico", content=comment)
                annot.set_colors(stroke=_BLUE_ANNOT)
                annot.update()
            except Exception:  # noqa: BLE001
                # fallback: caixa de texto no rodapé da área
                try:
                    box = fitz.Rect(
                        rect.x0,
                        min(rect.y1 + 2, page.rect.height - 36),
                        min(rect.x0 + 280, page.rect.width - 12),
                        min(rect.y1 + 34, page.rect.height - 8),
                    )
                    page.add_freetext_annot(
                        box,
                        comment[:220],
                        fontsize=8,
                        fontname="helv",
                        text_color=_BLUE_ANNOT,
                        fill_color=_BLUE_FILL,
                        border_color=_BLUE_ANNOT,
                    )
                except Exception:  # noqa: BLE001
                    return False
            return True
    return False


def _quote_candidates(quote: str) -> list[str]:
    cleaned = " ".join(quote.split())
    sizes = (160, 120, 90, 60, 40)
    out: list[str] = []
    for size in sizes:
        if len(cleaned) >= min(size, 12):
            piece = cleaned[:size].strip()
            if piece and piece not in out:
                out.append(piece)
    if cleaned and cleaned not in out:
        out.insert(0, cleaned)
    return out


def _append_summary_page(
    document,
    *,
    improvements: list[Improvement],
    unmatched: list[Improvement],
    anchored_count: int,
) -> None:
    import fitz

    page = document.new_page()
    margin = 48
    y = margin
    width = page.rect.width - 2 * margin

    def write(text: str, *, size: float = 11, bold: bool = False) -> None:
        nonlocal y
        font = "helv"
        # reportlab-like wrapping
        avg_char = size * 0.5
        max_chars = max(28, int(width / avg_char))
        for line in textwrap.wrap(text, width=max_chars) or [""]:
            if y > page.rect.height - margin:
                return
            page.insert_text(
                (margin, y),
                line,
                fontsize=size,
                fontname=font,
                color=(0.11, 0.14, 0.13),
            )
            y += size + 6

    write("Petição recriada — resumo de melhorias", size=14, bold=True)
    y += 6
    write(
        "Este PDF preserva o formato estrutural do documento original. "
        "Os trechos com melhorias propostas estão grifados em azul e "
        "recebem anotações (ícones/comentários) nas páginas anteriores."
    )
    y += 8
    write(
        f"Comentários ancorados no layout: {anchored_count} de {len(improvements)}."
    )
    y += 10

    if improvements:
        write("Melhorias propostas", size=12, bold=True)
        y += 4
        for index, item in enumerate(improvements, start=1):
            write(f"{index}. [{item.categoria}] {item.comentario}", size=10)
            if item.trecho.strip():
                write(f"   Trecho: “{item.trecho.strip()[:180]}”", size=9)
            y += 2

    if unmatched:
        y += 8
        write("Comentários sem âncora exata no PDF", size=12, bold=True)
        y += 4
        for index, item in enumerate(unmatched, start=1):
            write(f"{index}. [{item.categoria}] {item.comentario}", size=10)
            if item.trecho.strip():
                write(f"   Trecho citado: “{item.trecho.strip()[:180]}”", size=9)
            y += 2

    if not improvements and not unmatched:
        write(
            "Nenhuma melhoria automática foi inserida. O documento abaixo "
            "é a cópia estrutural do PDF original."
        )
