"""Cliente para Ollama local, especializado em sugerir melhorias de petição."""

from __future__ import annotations

import json
import re

import requests

from src.application.ports import LLMClientPort
from src.config.settings import OllamaSettings
from src.domain.entities import Improvement, ReviewResult, WebReference
from src.infrastructure.nlp.text_utils import short_excerpt

_VALID_CATEGORIES = {
    "fatos",
    "fundamentacao",
    "jurisprudencia",
    "provas",
    "pedidos",
    "estrutura",
    "clareza",
    "geral",
}


class OllamaClient(LLMClientPort):
    """Cliente HTTP para a API ``/api/generate`` do Ollama."""

    def __init__(self, settings: OllamaSettings) -> None:
        self._settings = settings

    def generate_improvements(
        self,
        original_text: str,
        review: ReviewResult,
        web_references: list[WebReference],
        model: str,
    ) -> list[Improvement]:
        prompt = self._build_prompt(original_text, review, web_references)
        raw = self._request(prompt, model)
        payload = self._parse_json(raw)
        return self._extract_improvements(payload)

    def _request(self, prompt: str, model: str) -> str:
        body = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._settings.temperature,
                "num_ctx": self._settings.num_ctx,
            },
        }
        response = requests.post(
            f"{self._settings.host.rstrip('/')}/api/generate",
            json=body,
            timeout=self._settings.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        text = str(data.get("response", "")).strip()
        if not text:
            raise RuntimeError("O Ollama respondeu sem texto.")
        return text

    @staticmethod
    def _build_prompt(
        original_text: str,
        review: ReviewResult,
        web_references: list[WebReference],
    ) -> str:
        rag_context = "\n\n".join(
            f"- {item.chunk.section} | {item.chunk.file_name}: "
            f"{short_excerpt(item.chunk.text, 700)}"
            for item in review.similar_chunks[:5]
        )
        problems = "\n".join(f"- {item}" for item in review.problems) or (
            "- Sem pontos críticos automáticos."
        )
        suggestions = "\n".join(f"- {item}" for item in review.suggestions) or (
            "- Reorganizar e fortalecer a estrutura."
        )
        references_block = _format_references(web_references)
        petition_excerpt = short_excerpt(original_text, 12000)
        return f"""
Você é um assistente jurídico brasileiro. Sua tarefa é apontar melhorias concretas em uma petição já existente, SEM reescrevê-la.

Responda SOMENTE com JSON válido, sem nenhum texto antes ou depois, no formato:
{{
  "melhorias": [
    {{
      "trecho": "trecho curto copiado literalmente da petição (15 a 40 palavras)",
      "comentario": "explicação objetiva da melhoria (1 a 3 frases)",
      "categoria": "fatos|fundamentacao|jurisprudencia|provas|pedidos|estrutura|clareza"
    }}
  ],
  "resumo": "frase curta resumindo o conjunto das melhorias propostas"
}}

Regras rígidas:
- NÃO reescreva a petição. NÃO retorne a petição inteira. Retorne apenas o JSON descrito.
- Cada item de "melhorias" deve apontar uma melhoria real e específica.
- "trecho" deve ser copiado IPSIS LITTERIS de dentro da petição abaixo (não invente nem parafraseie).
- Não invente fatos, datas, valores, jurisprudência, número de processo ou nome.
- Use a base RAG e as referências externas apenas como apoio para sugerir melhorias jurídicas válidas.
- Liste no mínimo 3 e no máximo 8 melhorias.
- Se a petição já estiver muito boa em algum ponto, ainda assim aponte melhorias acessórias (clareza, organização, anexos, jurisprudência atualizada genérica).

Pontos fracos detectados pela análise automática:
{problems}

Sugestões da análise automática:
{suggestions}

Base RAG (apoio para fundamentação genérica):
{rag_context}

Referências externas (apenas para inspirar sugestões; não copie textualmente):
{references_block}

Petição original (use apenas como fonte para os trechos literais):
\"\"\"
{petition_excerpt}
\"\"\"
""".strip()

    @staticmethod
    def _parse_json(raw: str) -> dict:
        block = _extract_json_block(raw)
        try:
            return json.loads(block)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"O Ollama não retornou JSON válido: {exc}. Resposta: {raw[:400]}"
            ) from exc

    @staticmethod
    def _extract_improvements(payload: dict) -> list[Improvement]:
        raw_items = payload.get("melhorias", [])
        improvements: list[Improvement] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            trecho = str(item.get("trecho", "")).strip()
            comentario = str(item.get("comentario", "")).strip()
            categoria = str(item.get("categoria", "geral")).strip() or "geral"
            if categoria not in _VALID_CATEGORIES:
                categoria = "geral"
            if not trecho or not comentario:
                continue
            improvements.append(
                Improvement(trecho=trecho, comentario=comentario, categoria=categoria)
            )
        return improvements


def _extract_json_block(text: str) -> str:
    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _format_references(web_references: list[WebReference]) -> str:
    if not web_references:
        return "Nenhuma referência externa foi encontrada."
    lines = []
    for index, reference in enumerate(web_references, start=1):
        lines.append(
            f"{index}. {reference.title}\nURL: {reference.url}\n"
            f"Resumo: {reference.snippet}"
        )
    return "\n\n".join(lines)
