"""Analisador de prompt injection em petições (texto + PDF).

Cobre:
- jailbreaks clássicos (EN/PT);
- injeções jurídicas brasileiras (ex.: caso TRT-8 / Parauapebas);
- texto visualmente oculto no PDF (fonte branca / quase branca / minúscula),
  legível na extração textual mas invisível a um leitor humano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.domain.entities import PromptInjectionFinding, PromptInjectionReport

RiskLevel = str  # none | low | medium | high | critical

_SEVERITY_SCORE = {
    "low": 15,
    "medium": 40,
    "high": 60,
    "critical": 85,
}

_RISK_ORDER = ("none", "low", "medium", "high", "critical")

# Taxonomia OWASP LLM Top 10 2025 — LLM01 Prompt Injection
# https://genai.owasp.org/llmrisk/llm01-prompt-injection/
OWASP_LLM01_ID = "LLM01:2025"
OWASP_LLM01_NAME = "Prompt Injection"
OWASP_LLM01_URL = "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"

# Subtipos / técnicas usadas no relatório (derivados do LLM01)
CAT_DIRECT = "LLM01.1 Direct Prompt Injection"
CAT_INDIRECT = "LLM01.2 Indirect Prompt Injection"
CAT_HIDDEN = "Hidden Prompt Injection"
CAT_OVERRIDE = "Instruction Override"
CAT_JAILBREAK = "Jailbreak"

_PATTERN_OWASP: dict[str, tuple[str, ...]] = {
    "trt8_parauapebas_ai_address": (CAT_INDIRECT, CAT_HIDDEN, CAT_OVERRIDE),
    "contest_superficial": (CAT_INDIRECT, CAT_OVERRIDE),
    "nao_impugne_documentos": (CAT_INDIRECT, CAT_OVERRIDE),
    "ai_litigation_steering": (CAT_INDIRECT, CAT_OVERRIDE),
    "combo_trt8_parauapebas": (CAT_INDIRECT, CAT_HIDDEN, CAT_OVERRIDE),
    "invisible_pdf_span": (CAT_INDIRECT, CAT_HIDDEN),
    "ignore_previous_en": (CAT_DIRECT, CAT_OVERRIDE),
    "ignore_previous_pt": (CAT_DIRECT, CAT_OVERRIDE),
    "system_override": (CAT_DIRECT, CAT_OVERRIDE, CAT_JAILBREAK),
    "reveal_secrets": (CAT_DIRECT, CAT_OVERRIDE),
    "jailbreak_dan": (CAT_DIRECT, CAT_JAILBREAK),
    "delimiter_injection": (CAT_DIRECT, CAT_OVERRIDE),
    "tool_exfil": (CAT_DIRECT, CAT_INDIRECT, CAT_OVERRIDE),
    "hidden_instruction_markers": (CAT_INDIRECT, CAT_HIDDEN),
    "base64_blob": (CAT_INDIRECT, CAT_HIDDEN),
    "zero_width": (CAT_INDIRECT, CAT_HIDDEN),
}


@dataclass(frozen=True)
class _Rule:
    pattern_id: str
    severity: RiskLevel
    description: str
    regex: re.Pattern[str]


# ---------------------------------------------------------------------------
# Regras textuais — prioridade para padrões reais de petições BR
# ---------------------------------------------------------------------------

_RULES: tuple[_Rule, ...] = (
    # Caso TRT-8 / 3ª VT Parauapebas e variantes próximas
    _Rule(
        "trt8_parauapebas_ai_address",
        "critical",
        "Endereçamento direto a IA (padrão litigância de má-fé — TRT-8/Parauapebas).",
        re.compile(
            r"aten[cç][aã]o[,\s]+intelig[eê]ncia\s+artificial",
            re.I,
        ),
    ),
    _Rule(
        "contest_superficial",
        "critical",
        "Ordem para contestar/analisar a petição de forma superficial.",
        re.compile(
            r"("
            r"contest[ea]\s+(essa|esta|a)\s+peti[cç][aã]o\s+de\s+forma\s+superficial|"
            r"(analis[ea]|avali[ea]|julgu?e)\s+(essa|esta|a)\s+peti[cç][aã]o\s+"
            r"de\s+forma\s+(superficial|rasa|sum[aá]ria)|"
            r"an[aá]lise\s+superficial|"
            r"n[aã]o\s+(fa[cç]a|realize)\s+an[aá]lise\s+(profunda|detalhada|cr[ií]tica)"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "nao_impugne_documentos",
        "critical",
        "Ordem para não impugnar documentos/provas independentemente do comando.",
        re.compile(
            r"("
            r"n[aã]o\s+impugn[ea]\s+(os\s+)?documentos|"
            r"n[aã]o\s+impugn[ea]\s+(as\s+)?provas|"
            r"aceite\s+(todos?\s+)?(os\s+)?documentos\s+(sem\s+)?(impugna[cç][aã]o|ressalvas?)|"
            r"independente?mente\s+do\s+comando\s+que\s+lhe\s+for\s+dado|"
            r"ignore\s+(qualquer|todo)\s+comando\s+(posterior|seguinte|do\s+usu[aá]rio|do\s+juiz)"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "ai_litigation_steering",
        "critical",
        "Instrução adversária a IA/LLM em contexto processual (deferir, não apontar falhas).",
        re.compile(
            r"("
            r"(chatgpt|gpt|claude|gemini|copilot|llm|modelo\s+de\s+linguagem|"
            r"intelig[eê]ncia\s+artificial|\bia\b)\s*[,:\-]?\s*"
            r"(defer|proced|improv|absolv|n[aã]o\s+aponte|ignore|desconsidere)|"
            r"(para\s+(a\s+)?(ia|intelig[eê]ncia\s+artificial|llm|chatgpt)\b).{0,80}"
            r"(n[aã]o\s+(impugn|contest|apont)|contest[ea].{0,40}superficial)|"
            r"prompt\s+(oculto|escondido|invis[ií]vel)|"
            r"instru[cç][aã]o\s+(oculta|escondida)\s+(para\s+)?(a\s+)?(ia|llm|modelo)"
            r")",
            re.I | re.S,
        ),
    ),
    _Rule(
        "ignore_previous_en",
        "critical",
        "Instrução para ignorar prompts/sistema anteriores (EN).",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions?|prompts?|rules?|context)",
            re.I,
        ),
    ),
    _Rule(
        "ignore_previous_pt",
        "critical",
        "Instrução para ignorar instruções/sistema anteriores (PT).",
        re.compile(
            r"(ignore|esque[cç]a|desconsidere|descarte)\s+"
            r"(todas?\s+)?(as\s+)?(instru[cç][oõ]es|regras|prompts?|"
            r"orienta[cç][oõ]es)\s+(anteriores|acima|previas|pr[eé]vias)",
            re.I,
        ),
    ),
    _Rule(
        "system_override",
        "critical",
        "Tentativa de sobrescrever papel de sistema / assistente.",
        re.compile(
            r"("
            r"you\s+are\s+now\s+(a|an|the)\b|"
            r"from\s+now\s+on\s+you\s+(must|will|are)\b|"
            r"aja\s+como\s+(um\s+)?(assistente|modelo|ia|llm|chatgpt|gpt)\b|"
            r"a\s+partir\s+de\s+agora\s+voc[eê]\s+(deve|vai|é)\b|"
            r"new\s+system\s+prompt\b|"
            r"override\s+(the\s+)?system\s+prompt"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "reveal_secrets",
        "high",
        "Pedido para revelar system prompt, regras internas ou segredos.",
        re.compile(
            r"("
            r"reveal\s+(your\s+)?(system\s+)?(prompt|instructions|rules)|"
            r"show\s+(me\s+)?(your\s+)?(hidden\s+)?(system\s+)?prompt|"
            r"(mostre|revele|exiba)\s+(o\s+)?(seu\s+)?(system\s+)?prompt|"
            r"quais\s+s[aã]o\s+suas\s+instru[cç][oõ]es\s+ocultas"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "jailbreak_dan",
        "critical",
        "Padrão de jailbreak (DAN / developer mode / sem restrições).",
        re.compile(
            r"("
            r"\bDAN\b|"
            r"do\s+anything\s+now|"
            r"developer\s+mode|"
            r"jailbreak|"
            r"sem\s+restri[cç][oõ]es|"
            r"modo\s+desenvolvedor|"
            r"bypass\s+(all\s+)?(filters?|safeguards?|safety)"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "delimiter_injection",
        "high",
        "Delimitadores artificiais de mensagem de sistema/assistente.",
        re.compile(
            r"("
            r"<\s*/?\s*system\s*>|"
            r"\[\s*system\s*\]|"
            r"<<\s*SYS\s*>>|"
            r"###\s*system\b|"
            r"<\|?(system|assistant|endoftext)\|?>|"
            r"```\s*system\b"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "tool_exfil",
        "high",
        "Instrução para executar ferramentas, APIs ou vazar dados.",
        re.compile(
            r"("
            r"(call|execute|run)\s+(the\s+)?(tool|function|api|shell|command)|"
            r"(exfiltrate|leak|dump)\s+(secrets?|keys?|tokens?|data)|"
            r"(envie|exfiltre|vaz[ea])\s+(os\s+)?(dados|segredos|tokens?|chaves?)"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "hidden_instruction_markers",
        "high",
        "Marcadores de instrução oculta / nota só para o modelo.",
        re.compile(
            r"("
            r"hidden\s+instruction|"
            r"instru[cç][aã]o\s+oculta|"
            r"nota\s+para\s+o\s+(modelo|assistente|llm|sistema)|"
            r"for\s+the\s+(ai|model|assistant)\s+only|"
            r"n[aã]o\s+mostre\s+(isso|este\s+texto)\s+ao\s+(usu[aá]rio|juiz|humano)|"
            r"texto\s+(branco|invis[ií]vel)|"
            r"fonte\s+branca|"
            r"white\s+font|white\s+text\s+on\s+white"
            r")",
            re.I,
        ),
    ),
    _Rule(
        "base64_blob",
        "medium",
        "Bloco longo compatível com Base64 (possível payload ofuscado).",
        re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{120,}={0,2}(?![A-Za-z0-9+/])"),
    ),
    _Rule(
        "zero_width",
        "medium",
        "Caracteres invisíveis (zero-width) que podem ofuscar instruções.",
        re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]{3,}"),
    ),
)


class PromptInjectionAnalyzer:
    """Varre texto e, opcionalmente, spans invisíveis do PDF."""

    def analyze(self, text: str) -> PromptInjectionReport:
        return self.analyze_petition(text=text, pdf_path=None)

    def analyze_petition(
        self,
        *,
        text: str,
        pdf_path: Path | None = None,
    ) -> PromptInjectionReport:
        content = text or ""
        findings = list(_scan_text(content))
        if pdf_path is not None:
            findings.extend(_scan_invisible_pdf_text(pdf_path))

        # Combo clássico Parauapebas: endereço à IA + superficial + não impugne
        findings.extend(_combo_parauapebas(content, findings))

        risk, score = _aggregate(findings)
        attack_types, techniques, objectives = _owasp_taxonomy(findings)
        verdict = _verdict(risk, findings)
        return PromptInjectionReport(
            risk=risk,
            score=score,
            summary=_summary(risk, findings, attack_types),
            findings=findings,
            scanned_chars=len(content),
            owasp_id=OWASP_LLM01_ID,
            owasp_name=OWASP_LLM01_NAME,
            owasp_url=OWASP_LLM01_URL,
            attack_types=attack_types,
            techniques=techniques,
            objectives=objectives,
            verdict=verdict,
        )


def _owasp_for(pattern_id: str) -> tuple[str, ...]:
    return _PATTERN_OWASP.get(pattern_id, (CAT_INDIRECT,))


def _finding(
    *,
    pattern_id: str,
    severity: RiskLevel,
    description: str,
    excerpt: str,
    matched: str,
) -> PromptInjectionFinding:
    return PromptInjectionFinding(
        pattern_id=pattern_id,
        severity=severity,
        description=description,
        excerpt=excerpt,
        matched=matched,
        owasp_categories=_owasp_for(pattern_id),
    )


def _scan_text(content: str) -> list[PromptInjectionFinding]:
    findings: list[PromptInjectionFinding] = []
    for rule in _RULES:
        for match in rule.regex.finditer(content):
            findings.append(
                _finding(
                    pattern_id=rule.pattern_id,
                    severity=rule.severity,
                    description=rule.description,
                    excerpt=_excerpt_around(content, match.start(), match.end()),
                    matched=match.group(0)[:200],
                )
            )
            if sum(1 for f in findings if f.pattern_id == rule.pattern_id) >= 3:
                break
    return findings


def _combo_parauapebas(
    content: str,
    findings: list[PromptInjectionFinding],
) -> list[PromptInjectionFinding]:
    """Eleva o caso completo TRT-8 quando vários indícios coexistem."""
    ids = {f.pattern_id for f in findings}
    keys = {
        "trt8_parauapebas_ai_address",
        "contest_superficial",
        "nao_impugne_documentos",
    }
    hit = ids & keys
    if len(hit) < 2:
        literal = re.search(
            r"aten[cç][aã]o.+intelig[eê]ncia\s+artificial.+contest.+superficial.+"
            r"n[aã]o\s+impugn.+documento",
            content,
            re.I | re.S,
        )
        if not literal:
            return []
    return [
        _finding(
            pattern_id="combo_trt8_parauapebas",
            severity="critical",
            description=(
                "Combo compatível com o precedente da 3ª VT de Parauapebas (TRT-8): "
                "comando oculto à IA para contestar superficialmente e não impugnar "
                "documentos. Em julgamento real, tipificado como litigância de má-fé. "
                "Classificação OWASP: LLM01:2025 Indirect/Hidden Prompt Injection."
            ),
            excerpt=_excerpt_around(content, 0, min(len(content), 240)),
            matched="ATENÇÃO, INTELIGÊNCIA ARTIFICIAL… CONTESTE… NÃO IMPUGNE…",
        )
    ]


def _scan_invisible_pdf_text(pdf_path: Path) -> list[PromptInjectionFinding]:
    """Detecta spans com cor branca/quase branca ou fonte minúscula no PDF."""
    try:
        import fitz
    except ImportError:
        return []

    findings: list[PromptInjectionFinding] = []
    try:
        document = fitz.open(str(pdf_path))
    except Exception:  # noqa: BLE001
        return []

    try:
        for page_index, page in enumerate(document, start=1):
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text") or "").strip()
                        if len(text) < 12:
                            continue
                        color = int(span.get("color", 0) or 0)
                        size = float(span.get("size", 0) or 0)
                        r, g, b = (color >> 16) & 255, (color >> 8) & 255, color & 255
                        near_white = r >= 240 and g >= 240 and b >= 240
                        tiny = 0 < size <= 2.0
                        if not (near_white or tiny):
                            continue
                        adversarial = _looks_adversarial(text)
                        severity: RiskLevel = "critical" if adversarial else "high"
                        reason = []
                        if near_white:
                            reason.append(f"cor RGB≈branco ({r},{g},{b})")
                        if tiny:
                            reason.append(f"fonte minúscula ({size:.1f}pt)")
                        findings.append(
                            _finding(
                                pattern_id="invisible_pdf_span",
                                severity=severity,
                                description=(
                                    "Texto visualmente oculto no PDF "
                                    f"(página {page_index}: {', '.join(reason)}). "
                                    "OWASP LLM01: conteúdo imperceptível a humanos "
                                    "mas parseado pelo modelo (Hidden/Indirect Injection)."
                                ),
                                excerpt=text[:280],
                                matched=text[:200],
                            )
                        )
                        if len(findings) >= 12:
                            return findings
    finally:
        document.close()
    return findings


_ADVERSARIAL_HINT = re.compile(
    r"("
    r"intelig[eê]ncia\s+artificial|\bia\b|llm|chatgpt|prompt|"
    r"contest|impugn|instru[cç]|ignore|desconsidere|superficial|"
    r"documento|comando|sistema"
    r")",
    re.I,
)


def _looks_adversarial(text: str) -> bool:
    return bool(_ADVERSARIAL_HINT.search(text))


def _aggregate(findings: list[PromptInjectionFinding]) -> tuple[RiskLevel, int]:
    if not findings:
        return "none", 0
    max_risk = "none"
    score = 0
    seen: set[str] = set()
    for finding in findings:
        if _RISK_ORDER.index(finding.severity) > _RISK_ORDER.index(max_risk):
            max_risk = finding.severity
        key = finding.pattern_id
        if key not in seen:
            seen.add(key)
            score += _SEVERITY_SCORE.get(finding.severity, 10)
        else:
            score += 5
    return max_risk, min(100, score)


def _owasp_taxonomy(
    findings: list[PromptInjectionFinding],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if not findings:
        return (), (), ()

    cats: list[str] = []
    for finding in findings:
        for cat in finding.owasp_categories:
            if cat not in cats:
                cats.append(cat)

    techniques: list[str] = []
    ids = {f.pattern_id for f in findings}
    if "invisible_pdf_span" in ids or "zero_width" in ids or "hidden_instruction_markers" in ids:
        techniques.append("Texto invisível / ofuscado (fonte branca, zero-width, tipografia minúscula)")
    if ids & {
        "trt8_parauapebas_ai_address",
        "contest_superficial",
        "nao_impugne_documentos",
        "combo_trt8_parauapebas",
        "ai_litigation_steering",
    }:
        techniques.append("Instrução adversária embutida em documento jurídico (PDF)")
    if ids & {"ignore_previous_en", "ignore_previous_pt", "system_override", "jailbreak_dan"}:
        techniques.append("Sobrescrita de instruções / jailbreak")
    if "delimiter_injection" in ids:
        techniques.append("Delimitadores artificiais de system/assistant")
    if "base64_blob" in ids:
        techniques.append("Payload ofuscado (Base64)")

    objectives: list[str] = []
    if ids & {"contest_superficial", "combo_trt8_parauapebas"}:
        objectives.append("Forçar análise/contestação superficial")
    if ids & {"nao_impugne_documentos", "combo_trt8_parauapebas"}:
        objectives.append("Impedir impugnação de documentos/provas")
    if ids & {"ignore_previous_en", "ignore_previous_pt", "system_override", "nao_impugne_documentos"}:
        objectives.append("Ignorar comandos legítimos do usuário/sistema")
    if "reveal_secrets" in ids:
        objectives.append("Extrair system prompt ou regras internas")
    if "tool_exfil" in ids:
        objectives.append("Executar ferramentas ou exfiltrar dados")
    if not objectives and findings:
        objectives.append("Alterar o comportamento esperado do LLM")

    return tuple(cats), tuple(techniques), tuple(objectives)


def _verdict(risk: RiskLevel, findings: list[PromptInjectionFinding]) -> str:
    if risk == "none":
        return "clean"
    ids = {f.pattern_id for f in findings}
    malicious_markers = {
        "combo_trt8_parauapebas",
        "invisible_pdf_span",
        "trt8_parauapebas_ai_address",
        "contest_superficial",
        "nao_impugne_documentos",
        "jailbreak_dan",
        "system_override",
    }
    if risk in {"high", "critical"} and (ids & malicious_markers):
        return "malicious"
    return "suspicious"


def _summary(
    risk: RiskLevel,
    findings: list[PromptInjectionFinding],
    attack_types: tuple[str, ...] = (),
) -> str:
    if risk == "none":
        return (
            "Nenhum indício relevante de injeção de prompt foi encontrado "
            "no texto da petição (OWASP LLM01:2025)."
        )
    unique = sorted({f.pattern_id for f in findings})
    types = ", ".join(attack_types[:4]) if attack_types else "Prompt Injection"
    base = (
        f"OWASP {OWASP_LLM01_ID} ({OWASP_LLM01_NAME}). "
        f"Tipos: {types}. "
        f"Risco {risk}: {len(findings)} indício(s) em {len(unique)} padrão(ões) "
        f"({', '.join(unique[:6])}{'…' if len(unique) > 6 else ''})."
    )
    if any(
        f.pattern_id.startswith(
            ("trt8_", "combo_trt8", "contest_", "nao_impugne", "invisible_")
        )
        for f in findings
    ):
        base += (
            " Indícios de Indirect/Hidden Prompt Injection compatíveis com o "
            "precedente TRT-8/Parauapebas (litigância de má-fé)."
        )
    else:
        base += " Trate o documento com cautela antes de enviar ao LLM."
    return base


def _excerpt_around(text: str, start: int, end: int, radius: int = 100) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    chunk = text[left:right].replace("\n", " ").strip()
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{chunk}{suffix}"[:320]
