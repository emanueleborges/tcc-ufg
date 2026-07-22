"""Adapter de busca web baseado em DuckDuckGo (DDGS)."""

from __future__ import annotations

try:
    from ddgs import DDGS
except ImportError:  # compatibilidade com versões antigas do pacote
    from duckduckgo_search import DDGS  # type: ignore[no-redef]

from src.application.ports import WebSearchPort
from src.config.settings import WebSearchSettings
from src.domain.entities import ReviewResult, WebReference


class DuckDuckGoWebSearch(WebSearchPort):
    """Cliente concreto que usa DDGS para buscar referências jurídicas."""

    def __init__(self, settings: WebSearchSettings) -> None:
        self._settings = settings

    def search_references(
        self,
        review: ReviewResult,
        max_results: int,
    ) -> list[WebReference]:
        return self._search(_build_review_queries(review), max_results)

    def search_text(
        self,
        query: str,
        max_results: int,
    ) -> list[WebReference]:
        if not query.strip():
            return []
        return self._search([query.strip()], max_results)

    def _search(self, queries: list[str], max_results: int) -> list[WebReference]:
        references: list[WebReference] = []
        seen_urls: set[str] = set()
        with DDGS() as ddgs:
            for query in queries:
                if len(references) >= max_results:
                    break
                try:
                    results = ddgs.text(
                        query,
                        region=self._settings.region,
                        safesearch=self._settings.safesearch,
                        max_results=max_results,
                    )
                except Exception:  # noqa: BLE001 - DDGS pode falhar por rate-limit
                    continue
                for result in results:
                    url = result.get("href") or result.get("url") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    references.append(
                        WebReference(
                            title=str(result.get("title", "")).strip(),
                            url=url,
                            snippet=str(result.get("body", "")).strip(),
                        )
                    )
                    if len(references) >= max_results:
                        break
        return references


def _build_review_queries(review: ReviewResult) -> list[str]:
    queries = [
        "petição inicial dano moral responsabilidade civil jurisprudência recente",
        "indenização por dano moral petição inicial fundamentos pedidos provas",
    ]
    if review.problems:
        focus = " ".join(review.problems[:2])
        queries.append(f"petição inicial {focus} jurisprudência")
    return queries
