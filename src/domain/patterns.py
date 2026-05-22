"""Padrões linguísticos jurídicos usados pelas heurísticas de domínio.

Estes padrões pertencem ao domínio porque expressam o conhecimento
jurídico essencial do sistema: como identificar seções, features e
indicadores de procedência em petições brasileiras.
"""

from __future__ import annotations

SECTION_PATTERNS: dict[str, list[str]] = {
    "cabecalho": [
        r"excelent[íi]ssim[ao]",
        r"ju[íi]z[ao]? de direito",
        r"vara (c[íi]vel|do trabalho|federal)",
    ],
    "qualificacao": [
        r"qualifica[çc][ãa]o",
        r"brasileir[ao]",
        r"inscrit[ao] no cpf",
        r"pessoa jur[íi]dica",
    ],
    "fatos": [
        r"dos fatos",
        r"s[íi]ntese f[áa]tica",
        r"da narrativa f[áa]tica",
        r"breve relato",
    ],
    "fundamentacao": [
        r"do direito",
        r"dos fundamentos",
        r"fundamenta[çc][ãa]o jur[íi]dica",
        r"m[ée]rito",
    ],
    "dano_moral": [
        r"do dano moral",
        r"danos morais",
        r"indeniza[çc][ãa]o por dano moral",
    ],
    "jurisprudencia": [
        r"jurisprud[êe]ncia",
        r"precedentes",
        r"entendimento jurisprudencial",
        r"tribunal de justi[çc]a",
        r"superior tribunal de justi[çc]a",
        r"stj",
        r"stf",
    ],
    "provas": [
        r"das provas",
        r"protesta provar",
        r"documentos anexos",
        r"prova documental",
    ],
    "tutela": [
        r"tutela de urg[êe]ncia",
        r"tutela antecipada",
        r"liminar",
    ],
    "pedidos": [
        r"dos pedidos",
        r"requer",
        r"requerimentos",
        r"ante o exposto",
    ],
    "fechamento": [
        r"termos em que",
        r"pede deferimento",
        r"d[áa]-se [àa] causa",
    ],
}

FEATURE_PATTERNS: dict[str, str] = {
    "artigos_legais": r"\b(art\.?|artigo)\s*\d+[\wº°-]*",
    "jurisprudencias": (
        r"\b(stj|stf|tj[a-z]{2}|trf\d?|tst|recurso|"
        r"apela[çc][ãa]o|agravo|ac[óo]rd[ãa]o)\b"
    ),
    "constitucional": r"constitui[çc][ãa]o|\bcf\b|art\.\s*5[º°]",
    "cdc": r"c[óo]digo de defesa do consumidor|\bcdc\b|consumidor",
    "codigo_civil": (
        r"c[óo]digo civil|\bcc\b|responsabilidade civil|ato il[íi]cito"
    ),
    "provas": (
        r"prova|documento|anexo|print|comprovante|testemunha|per[íi]cia"
    ),
    "pedidos_subsidiarios": r"subsidiariamente|sucessivamente|alternativamente",
    "valor_dano_moral": (
        r"dano moral[^\n]{0,120}r\$|r\$[^\n]{0,120}dano moral"
    ),
    "tutela_urgencia": r"tutela de urg[êe]ncia|liminar|tutela antecipada",
    "gratuidade": (
        r"gratuidade da justi[çc]a|justi[çc]a gratuita|hipossufici[êe]ncia"
    ),
}

PETITION_TERMS: list[str] = [
    "petição inicial",
    "acao de indenizacao",
    "ação de indenização",
    "indenização por dano moral",
    "indenizacao por dano moral",
    "danos morais",
    "dano moral",
]

FAVORABLE_TERMS: list[str] = [
    "julgo procedente",
    "julgo parcialmente procedente",
    "pedido procedente",
    "pedidos procedentes",
    "procedência do pedido",
    "procedencia do pedido",
    "ganho de causa",
    "sentença de procedência",
    "sentenca de procedencia",
    "recurso provido",
    "provimento ao recurso",
    "provimento parcial ao recurso",
]

NEGATIVE_TERMS: list[str] = [
    "julgo improcedente",
    "pedido improcedente",
    "pedidos improcedentes",
    "improcedência do pedido",
    "improcedencia do pedido",
    "extingo o processo sem resolução do mérito",
    "extingo o processo sem resolucao do merito",
]
