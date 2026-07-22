"""Classificador heurístico de intenção das mensagens do chat.

A classificação ocorre em três níveis, do mais determinístico ao mais
inferencial:

1. **Ações sobre petição** (quando há PDF anexado e um verbo de análise/
   recriação).
2. **Roteamento explícito**: o usuário usa palavras como "internet",
   "pesquise", "base RAG", "compare com" — decisão imediata.
3. **Roteamento automático por sinais**: a mensagem não tem palavra-chave
   óbvia, mas contém sinais temporais (datas, "atual", "recente") ou
   substância jurídica (termos como "dano moral", "art.", "STJ", "CDC").
   Saudações e perguntas curtas caem em conversa geral (Ollama).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.domain.chat import Intent
from src.infrastructure.nlp.text_utils import normalize_for_search


class RoutingMode(str, Enum):
    """Indica como a decisão foi tomada."""

    EXPLICIT = "explicit"
    AUTOMATIC = "automatic"
    DEFAULT = "default"

    @property
    def label(self) -> str:
        return {
            RoutingMode.EXPLICIT: "explícito",
            RoutingMode.AUTOMATIC: "automático",
            RoutingMode.DEFAULT: "padrão",
        }[self]


# ---------------------------------------------------------------------------
# Petição: ações explícitas quando há PDF anexado.
# ---------------------------------------------------------------------------

_ANALYZE_KEYWORDS = (
    "analise",
    "analisar",
    "analisa",
    "avalie",
    "avaliar",
    "avalia",
    "critique",
    "criticar",
    "critica",
    "revise",
    "revisar",
    "revisao",
    "diagnostico",
    "score",
    "pontos fracos",
    "feedback",
    "como esta",
    "qualidade",
)

_RECREATE_KEYWORDS = (
    "recrie",
    "recriar",
    "recreate",
    "reescreva",
    "reescrever",
    "melhore",
    "melhorar",
    "aprimore",
    "aprimorar",
    "refazer",
    "refaca",
    "reformule",
    "reformular",
    "comente",
    "comentarios inline",
    "anote",
)

# ---------------------------------------------------------------------------
# Roteamento explícito (alta confiança).
# ---------------------------------------------------------------------------

_EXPLICIT_INTERNET_KEYWORDS = (
    "internet",
    "web",
    "online",
    "google",
    "duckduckgo",
    "ddg",
    "pesquise",
    "pesquisa",
    "busque na internet",
    "buscar na internet",
    "navega na web",
    "pesquise online",
)

_EXPLICIT_RAG_KEYWORDS = (
    "base",
    "corpus",
    "rag",
    "base interna",
    "indice",
    "peticoes anteriores",
    "documentos da base",
    "compare com a base",
    "exemplo da base",
    "modelo da base",
    "jurisprudencia da base",
)

# ---------------------------------------------------------------------------
# Sinais automáticos.
# ---------------------------------------------------------------------------

# 1) Sinais temporais → Internet (informação atual/recente).
_TEMPORAL_KEYWORDS = (
    "hoje",
    "agora",
    "atualmente",
    "atual",
    "neste momento",
    "ultima",
    "ultimo",
    "ultimas",
    "ultimos",
    "ultimamente",
    "recente",
    "recentemente",
    "noticia",
    "noticias",
    "novidade",
    "novidades",
    "tendencia",
    "tendencias",
    "atualizado",
    "atualizada",
    "novo",
    "nova",
    "este ano",
    "esse ano",
    "este mes",
    "esse mes",
)

_YEAR_PATTERN = re.compile(r"\b(20[2-3]\d|19\d{2})\b")

# 2) Sinais jurídicos substantivos → RAG (domínio do TCC).
_JURIDICAL_KEYWORDS = (
    "peticao",
    "peticoes",
    "inicial",
    "exordial",
    "dano moral",
    "danos morais",
    "dano material",
    "indenizacao",
    "indenizatoria",
    "responsabilidade civil",
    "ato ilicito",
    "nexo causal",
    "jurisprudencia",
    "precedente",
    "precedentes",
    "acordao",
    "acordaos",
    "stj",
    "stf",
    "trf",
    "tjsp",
    "tjmg",
    "tjrj",
    "tst",
    "codigo civil",
    "codigo de defesa do consumidor",
    "cdc",
    "constituicao",
    "tutela de urgencia",
    "tutela antecipada",
    "liminar",
    "ressarcimento",
    "reparacao",
    "honorarios",
    "sentenca",
    "recurso",
    "apelacao",
    "agravo",
    "magistrado",
    "ministro",
    "desembargador",
    "juizado",
    "vara civel",
    "tribunal de justica",
    "tribunal superior",
    "consumidor",
)

_ARTICLE_REFERENCE_PATTERN = re.compile(
    r"\b(art\.?|artigo)\s*\d+", flags=re.IGNORECASE
)

# 3) Saudações e mensagens muito curtas → Ollama (conversa casual).
_GREETING_KEYWORDS = (
    "oi",
    "ola",
    "ola!",
    "tudo bem",
    "bom dia",
    "boa tarde",
    "boa noite",
    "obrigado",
    "obrigada",
    "valeu",
    "tchau",
    "ate logo",
    "como vai",
    "quem e voce",
    "o que voce faz",
    "ajuda",
    "help",
)

_MIN_WORDS_FOR_AUTO_ROUTE = 3


@dataclass(frozen=True)
class ClassifiedIntent:
    """Resultado da classificação heurística."""

    intent: Intent
    reason: str
    mode: RoutingMode = RoutingMode.DEFAULT


def classify_intent(message: str, *, has_petition: bool) -> ClassifiedIntent:
    """Detecta a intenção dominante e a fonte ideal para a mensagem."""
    normalized = normalize_for_search(message)
    word_count = len(re.findall(r"\w+", normalized))

    if has_petition and _contains_any(normalized, _RECREATE_KEYWORDS):
        return ClassifiedIntent(
            intent=Intent.RECREATE_PETITION,
            reason="Pedido de recriação/melhoria com petição anexada.",
            mode=RoutingMode.EXPLICIT,
        )
    if has_petition and _contains_any(normalized, _ANALYZE_KEYWORDS):
        return ClassifiedIntent(
            intent=Intent.ANALYZE_PETITION,
            reason="Pedido de análise/avaliação com petição anexada.",
            mode=RoutingMode.EXPLICIT,
        )

    if _contains_any(normalized, _EXPLICIT_INTERNET_KEYWORDS):
        return ClassifiedIntent(
            intent=Intent.ASK_INTERNET,
            reason="Pedido explícito de busca na internet.",
            mode=RoutingMode.EXPLICIT,
        )
    if _contains_any(normalized, _EXPLICIT_RAG_KEYWORDS):
        return ClassifiedIntent(
            intent=Intent.ASK_RAG,
            reason="Pedido explícito de uso da base RAG.",
            mode=RoutingMode.EXPLICIT,
        )

    if _is_casual(normalized, word_count):
        return ClassifiedIntent(
            intent=Intent.ASK_OLLAMA,
            reason="Saudação ou mensagem curta — conversa casual.",
            mode=RoutingMode.AUTOMATIC,
        )

    is_temporal = _has_temporal_signal(normalized)
    is_juridical = _has_juridical_signal(normalized)

    if is_temporal and not is_juridical:
        return ClassifiedIntent(
            intent=Intent.ASK_INTERNET,
            reason="Sinais temporais detectados — informação atual/recente vem da internet.",
            mode=RoutingMode.AUTOMATIC,
        )
    if is_temporal and is_juridical:
        return ClassifiedIntent(
            intent=Intent.ASK_INTERNET,
            reason="Tema jurídico recente — internet prioriza atualidade da informação.",
            mode=RoutingMode.AUTOMATIC,
        )
    if is_juridical:
        return ClassifiedIntent(
            intent=Intent.ASK_RAG,
            reason="Tema jurídico substantivo — base RAG é a fonte mais confiável.",
            mode=RoutingMode.AUTOMATIC,
        )

    return ClassifiedIntent(
        intent=Intent.ASK_OLLAMA,
        reason="Sem sinais específicos — conversa geral via LLM local.",
        mode=RoutingMode.DEFAULT,
    )


def _contains_any(normalized: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in normalized for keyword in keywords)


def _has_temporal_signal(normalized: str) -> bool:
    if _contains_any(normalized, _TEMPORAL_KEYWORDS):
        return True
    return bool(_YEAR_PATTERN.search(normalized))


def _has_juridical_signal(normalized: str) -> bool:
    if _contains_any(normalized, _JURIDICAL_KEYWORDS):
        return True
    return bool(_ARTICLE_REFERENCE_PATTERN.search(normalized))


def _is_casual(normalized: str, word_count: int) -> bool:
    if word_count <= 2:
        return True
    return _contains_any(normalized, _GREETING_KEYWORDS) and word_count < _MIN_WORDS_FOR_AUTO_ROUTE + 2
