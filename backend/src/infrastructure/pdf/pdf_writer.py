"""Conversor de markdown em PDF usando reportlab."""

from __future__ import annotations

import re
import textwrap
from html import escape
from pathlib import Path

from src.application.ports import PdfWriterPort
from src.infrastructure.nlp.text_utils import strip_markdown_inline

_WRAP_WIDTH = 105


class ReportlabPdfWriter(PdfWriterPort):
    """Converte markdown simples em PDF A4 via reportlab."""

    def markdown_to_pdf(self, markdown: str, output_path: Path) -> Path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        except ImportError as exc:
            raise RuntimeError(
                "Instale a dependência reportlab para gerar PDF: pip install reportlab"
            ) from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        styles = getSampleStyleSheet()
        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        story = []
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 8))
                continue
            style_name, line = self._resolve_style(line)
            line = strip_markdown_inline(line)
            wrapped = "<br/>".join(
                escape(part) for part in textwrap.wrap(line, width=_WRAP_WIDTH) or [""]
            )
            story.append(Paragraph(wrapped, styles[style_name]))
        document.build(story)
        return output_path

    @staticmethod
    def _resolve_style(line: str) -> tuple[str, str]:
        if line.startswith("# "):
            return "Title", line[2:].strip()
        if line.startswith("## "):
            return "Heading2", line[3:].strip()
        if line.startswith("### "):
            return "Heading3", line[4:].strip()
        if line.startswith("#### "):
            return "Heading4", line[5:].strip()
        if re.match(r"^[-*]\s+", line):
            return "BodyText", "• " + re.sub(r"^[-*]\s+", "", line)
        if line.startswith(">"):
            return "BodyText", line.lstrip("> ").strip()
        return "BodyText", line
