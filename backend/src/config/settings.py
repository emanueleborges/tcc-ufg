"""Configurações centralizadas da aplicação.

Toda configuração mutável fica aqui, agrupada por contexto. As constantes
de domínio (padrões linguísticos jurídicos) ficam em ``src.domain.patterns``.

Variáveis de ambiente sobrepõem os valores padrão, permitindo configurar
o sistema em produção sem mexer no código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _project_root() -> Path:
    """Raiz do backend (dois níveis acima deste arquivo: backend/)."""
    return Path(__file__).resolve().parents[2]


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value and value.isdigit() else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class PathsSettings:
    """Caminhos do sistema de arquivos usados pelo projeto."""

    root: Path = field(default_factory=_project_root)
    downloads_dir: Path = field(default_factory=lambda: _project_root() / "downloads_peticoes")
    index_dir: Path = field(default_factory=lambda: _project_root() / "indice_juridico")
    reports_dir: Path = field(default_factory=lambda: _project_root() / "relatorios")
    uploads_dir: Path = field(default_factory=lambda: _project_root() / "uploads")
    validations_dir: Path = field(default_factory=lambda: _project_root() / "validacoes")

    @property
    def accepted_pdfs_dir(self) -> Path:
        return self.downloads_dir / "aceitas"

    @property
    def rejected_pdfs_dir(self) -> Path:
        return self.downloads_dir / "rejeitadas"

    @property
    def partial_pdfs_dir(self) -> Path:
        return self.downloads_dir / "parcial"


@dataclass(frozen=True)
class ScrapingSettings:
    """Parâmetros do baixador de PDFs públicos."""

    download_limit: int = field(
        default_factory=lambda: _env_int("SCRAPING_DOWNLOAD_LIMIT", 100)
    )
    min_corpus_size: int = field(
        default_factory=lambda: _env_int("SCRAPING_MIN_CORPUS_SIZE", 100)
    )
    max_results: int = field(default_factory=lambda: _env_int("SCRAPING_MAX_RESULTS", 40))
    max_links_per_page: int = field(
        default_factory=lambda: _env_int("SCRAPING_MAX_LINKS_PER_PAGE", 24)
    )
    http_timeout: int = field(default_factory=lambda: _env_int("SCRAPING_HTTP_TIMEOUT", 25))
    request_pause: float = field(
        default_factory=lambda: _env_float("SCRAPING_REQUEST_PAUSE", 0.6)
    )
    search_pause: float = field(
        default_factory=lambda: _env_float("SCRAPING_SEARCH_PAUSE", 1.2)
    )
    # DDGS costuma falhar por DNS/captcha; HTML DDG/Brave é o caminho padrão.
    use_ddgs: bool = field(default_factory=lambda: _env_bool("SCRAPING_USE_DDGS", False))
    # Sempre persiste aceitas e rejeitadas (pode forçar False só via env em emergência).
    keep_rejected: bool = field(
        default_factory=lambda: _env_bool("SCRAPING_KEEP_REJECTED", True)
    )
    max_runtime_seconds: int = field(
        default_factory=lambda: _env_int("SCRAPING_MAX_RUNTIME_SECONDS", 45 * 60)
    )
    max_file_size_bytes: int = field(
        default_factory=lambda: _env_int("SCRAPING_MAX_FILE_SIZE_BYTES", 30 * 1024 * 1024)
    )
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    # Queries simples: aspas excessivas zeram recall no DDG/Brave HTML.
    queries: tuple[str, ...] = (
        # Procedentes / deferidos
        "peticao inicial dano moral filetype:pdf",
        "julgo procedente dano moral peticao filetype:pdf",
        "sentenca procedente indenizacao dano moral pdf",
        "procedencia do pedido dano moral filetype:pdf",
        "acao indenizatoria consumidor negativacao pdf",
        "danos morais condeno peticao inicial pdf",
        "tjmg dano moral procedente filetype:pdf",
        "conjur peticao inicial danos morais pdf",
        # Improcedentes / indeferidos (rejeitadas/)
        "julgo improcedente dano moral filetype:pdf",
        "indenizacao danos morais improcedente pdf",
        "improcedencia do pedido dano moral filetype:pdf",
        "recurso desprovido danos morais pdf",
        "nego provimento indenizacao dano moral pdf",
        "indeferimento peticao inicial dano moral pdf",
        "tutela urgencia indeferida dano moral pdf",
        "tjrj dano moral improcedente filetype:pdf",
        "acordao dano moral nao provido pdf",
        "sentenca juizado especial dano moral improcedente pdf",
        # Parcialmente procedentes (parcial/)
        "julgo parcialmente procedente dano moral filetype:pdf",
        "procedencia parcial indenizacao dano moral pdf",
        "provimento parcial danos morais filetype:pdf",
        "parcialmente procedente peticao inicial pdf",
    )


@dataclass(frozen=True)
class RagSettings:
    """Parâmetros do motor RAG."""

    embedding_model: str = field(
        default_factory=lambda: os.getenv("RAG_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    )
    top_k_similares: int = field(default_factory=lambda: _env_int("RAG_TOP_K", 8))
    max_chunk_chars: int = field(default_factory=lambda: _env_int("RAG_MAX_CHUNK_CHARS", 1800))
    min_chunk_chars: int = field(default_factory=lambda: _env_int("RAG_MIN_CHUNK_CHARS", 250))
    anonymize: bool = field(default_factory=lambda: _env_bool("RAG_ANONYMIZE", True))
    embedding_batch_size: int = field(default_factory=lambda: _env_int("RAG_EMBEDDING_BATCH_SIZE", 16))


@dataclass(frozen=True)
class OllamaSettings:
    """Parâmetros para integração com Ollama local."""

    host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    default_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
    timeout_seconds: int = field(default_factory=lambda: _env_int("OLLAMA_TIMEOUT", 240))
    temperature: float = field(default_factory=lambda: _env_float("OLLAMA_TEMPERATURE", 0.2))
    num_ctx: int = field(default_factory=lambda: _env_int("OLLAMA_NUM_CTX", 8192))


@dataclass(frozen=True)
class WebSearchSettings:
    """Parâmetros de busca web (DuckDuckGo)."""

    region: str = field(default_factory=lambda: os.getenv("WEB_SEARCH_REGION", "br-pt"))
    safesearch: str = field(default_factory=lambda: os.getenv("WEB_SEARCH_SAFESEARCH", "moderate"))
    max_results: int = field(default_factory=lambda: _env_int("WEB_SEARCH_MAX_RESULTS", 5))


@dataclass(frozen=True)
class Settings:
    """Configuração raiz, agregando todos os contextos."""

    paths: PathsSettings = field(default_factory=PathsSettings)
    scraping: ScrapingSettings = field(default_factory=ScrapingSettings)
    rag: RagSettings = field(default_factory=RagSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    web_search: WebSearchSettings = field(default_factory=WebSearchSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna a instância singleton de configuração."""
    return Settings()
