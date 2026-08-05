"""Âncoras jurídicas curtas para grounding de modelos pequenos.

Modelos como llama3.2:1b ignoram system prompts longos e alucinam institutos
clássicos. Quando a pergunta casa com um padrão conhecido, injetamos um
bloco de fatos obrigatórios no turno do usuário — e, em modelos muito
pequenos, podemos responder direto a partir da âncora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LegalAnchor:
    id: str
    persona_ids: frozenset[str]
    patterns: tuple[re.Pattern[str], ...]
    facts: str
    direct_answer: str


_ANCHORS: tuple[LegalAnchor, ...] = (
    LegalAnchor(
        id="cp_art15_desistencia_arrependimento",
        persona_ids=frozenset({"penal", "geral"}),
        patterns=(
            re.compile(r"desist[eê]ncia\s+volunt[aá]ria", re.I),
            re.compile(r"arrependimento\s+efic", re.I),
            re.compile(
                r"art\.?\s*15.*c[oó]digo\s+penal|c[oó]digo\s+penal.*art\.?\s*15",
                re.I,
            ),
        ),
        facts=(
            "BASE JURÍDICA OBRIGATÓRIA (não contradiga):\n"
            "- Fundamento: art. 15 do Código Penal (fase de tentativa).\n"
            "- Desistência voluntária: o agente desiste voluntariamente de prosseguir "
            "nos atos de execução.\n"
            "- Arrependimento eficaz: após esgotar a execução, o agente impede o "
            "resultado por ato voluntário.\n"
            "- Consequência comum: não se pune a tentativa; o agente responde apenas "
            "pelos atos já praticados, se constituírem crime autônomo.\n"
            "- Não confundir com: desistência da ação penal; arrependimento posterior "
            "(art. 16 CP — redução de pena em crimes patrimoniais sem violência/grave ameaça).\n"
            "Estruture a resposta com: (1) diferença entre os institutos; "
            "(2) consequência jurídica de cada um; (3) distinção do art. 16."
        ),
        direct_answer=(
            "## Desistência voluntária × arrependimento eficaz (art. 15 do CP)\n\n"
            "Ambos os institutos estão no **art. 15 do Código Penal** e operam na "
            "**fase de tentativa**. A diferença está no momento em que o agente age:\n\n"
            "### Desistência voluntária\n"
            "O agente **desiste voluntariamente de prosseguir** nos atos de execução "
            "(ainda não esgotou a execução).\n\n"
            "### Arrependimento eficaz\n"
            "O agente **já esgotou a execução**, mas **impede o resultado** por ato "
            "voluntário ulterior.\n\n"
            "### Consequência jurídica (comum aos dois)\n"
            "**Não se pune a tentativa.** O agente responde apenas pelos atos já "
            "praticados, **se** esses atos constituírem **crime autônomo**.\n\n"
            "### Atenção — não confundir\n"
            "- **Não** se trata de desistência da ação penal.\n"
            "- **Arrependimento posterior** (art. 16 do CP) é instituto distinto: "
            "reparação do dano ou restituição da coisa até o recebimento da denúncia/"
            "queixa, com **redução de pena** em crimes patrimoniais sem violência "
            "ou grave ameaça.\n"
        ),
    ),
)

_TINY_MODEL_RE = re.compile(r"(?:[:\-_/]|^)([123]b)\b", re.I)


def find_legal_anchor(user_message: str, persona_id: str | None) -> LegalAnchor | None:
    pid = (persona_id or "geral").strip().lower()
    text = user_message or ""
    for anchor in _ANCHORS:
        if pid not in anchor.persona_ids:
            continue
        if any(pattern.search(text) for pattern in anchor.patterns):
            return anchor
    return None


def is_tiny_model(model: str | None) -> bool:
    if not model:
        return False
    return bool(_TINY_MODEL_RE.search(model.strip()))
