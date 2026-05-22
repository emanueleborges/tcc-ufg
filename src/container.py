"""Composition root: monta o grafo de dependências da aplicação.

Aqui é o único lugar onde implementações concretas se conectam aos
ports (interfaces). Toda a aplicação consome serviços via ``AppContainer``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from src.application.use_cases import (
    AnalyzePetitionUseCase,
    BuildIndexUseCase,
    ChatWithAssistantUseCase,
    DownloadPetitionsUseCase,
    GenerateCorpusReportUseCase,
    LoadOrBuildIndexUseCase,
    RecreatePetitionUseCase,
)
from src.config.settings import Settings, get_settings
from src.domain.chat import Intent
from src.infrastructure.langchain.ollama_chat import LangChainOllamaChat
from src.infrastructure.llm.ollama_client import OllamaClient
from src.infrastructure.nlp.embedding_engine import SentenceTransformerEmbeddingEngine
from src.infrastructure.pdf.pdf_reader import PdfReader
from src.infrastructure.pdf.pdf_writer import ReportlabPdfWriter
from src.infrastructure.persistence.index_repository import FileSystemIndexRepository
from src.infrastructure.scraping.pdf_scraper import PdfScraper
from src.infrastructure.search.duckduckgo_search import DuckDuckGoWebSearch
from src.services.chat.internet_answerer import InternetAnswerer
from src.services.chat.ollama_answerer import OllamaAnswerer
from src.services.chat.orchestrator import ChatOrchestrator
from src.services.chat.petition_answerers import (
    AnalyzePetitionAnswerer,
    RecreatePetitionAnswerer,
)
from src.services.chat.rag_answerer import RagAnswerer
from src.services.chunk_factory import ChunkFactory
from src.services.semantic_search import SemanticSearchService


@dataclass
class AppContainer:
    """Container de dependências da aplicação (injeção manual e lazy)."""

    settings: Settings

    @classmethod
    def default(cls) -> "AppContainer":
        return cls(settings=get_settings())

    # ----- adapters de infraestrutura -----
    @cached_property
    def pdf_reader(self) -> PdfReader:
        return PdfReader()

    @cached_property
    def pdf_writer(self) -> ReportlabPdfWriter:
        return ReportlabPdfWriter()

    @cached_property
    def embedding_engine(self) -> SentenceTransformerEmbeddingEngine:
        return SentenceTransformerEmbeddingEngine(
            model_name=self.settings.rag.embedding_model,
            batch_size=self.settings.rag.embedding_batch_size,
        )

    @cached_property
    def index_repository(self) -> FileSystemIndexRepository:
        return FileSystemIndexRepository(self.settings.paths.index_dir)

    @cached_property
    def llm_client(self) -> OllamaClient:
        return OllamaClient(self.settings.ollama)

    @cached_property
    def web_search(self) -> DuckDuckGoWebSearch:
        return DuckDuckGoWebSearch(self.settings.web_search)

    @cached_property
    def pdf_scraper(self) -> PdfScraper:
        return PdfScraper(self.settings.paths, self.settings.scraping)

    # ----- services -----
    @cached_property
    def chunk_factory(self) -> ChunkFactory:
        return ChunkFactory(self.pdf_reader, self.settings.rag)

    @cached_property
    def semantic_search(self) -> SemanticSearchService:
        return SemanticSearchService(self.embedding_engine)

    # ----- use cases -----
    @cached_property
    def build_index_use_case(self) -> BuildIndexUseCase:
        return BuildIndexUseCase(
            chunk_factory=self.chunk_factory,
            embedding_engine=self.embedding_engine,
            index_repository=self.index_repository,
            paths=self.settings.paths,
        )

    @cached_property
    def load_or_build_index_use_case(self) -> LoadOrBuildIndexUseCase:
        return LoadOrBuildIndexUseCase(
            index_repository=self.index_repository,
            build_index_use_case=self.build_index_use_case,
        )

    @cached_property
    def analyze_petition_use_case(self) -> AnalyzePetitionUseCase:
        return AnalyzePetitionUseCase(
            chunk_factory=self.chunk_factory,
            semantic_search=self.semantic_search,
            rag_settings=self.settings.rag,
        )

    @cached_property
    def recreate_petition_use_case(self) -> RecreatePetitionUseCase:
        return RecreatePetitionUseCase(
            pdf_reader=self.pdf_reader,
            llm_client=self.llm_client,
            web_search=self.web_search,
            web_search_settings=self.settings.web_search,
        )

    @cached_property
    def download_petitions_use_case(self) -> DownloadPetitionsUseCase:
        return DownloadPetitionsUseCase(self.pdf_scraper)

    @cached_property
    def generate_corpus_report_use_case(self) -> GenerateCorpusReportUseCase:
        return GenerateCorpusReportUseCase(self.settings.paths)

    # ----- chatbot (LangChain) -----
    @cached_property
    def conversational_llm(self) -> LangChainOllamaChat:
        return LangChainOllamaChat(self.settings.ollama)

    @cached_property
    def chat_orchestrator(self) -> ChatOrchestrator:
        ollama = OllamaAnswerer(self.conversational_llm)
        rag = RagAnswerer(
            llm=self.conversational_llm,
            semantic_search=self.semantic_search,
            load_or_build_index=self.load_or_build_index_use_case,
            rag_settings=self.settings.rag,
        )
        internet = InternetAnswerer(
            llm=self.conversational_llm,
            web_search=self.web_search,
            web_search_settings=self.settings.web_search,
        )
        analyze = AnalyzePetitionAnswerer(
            load_or_build_index=self.load_or_build_index_use_case,
            analyze_petition=self.analyze_petition_use_case,
        )
        recreate = RecreatePetitionAnswerer(
            load_or_build_index=self.load_or_build_index_use_case,
            analyze_petition=self.analyze_petition_use_case,
            recreate_petition=self.recreate_petition_use_case,
        )
        return ChatOrchestrator(
            {
                Intent.ASK_OLLAMA: ollama,
                Intent.ASK_RAG: rag,
                Intent.ASK_INTERNET: internet,
                Intent.ANALYZE_PETITION: analyze,
                Intent.RECREATE_PETITION: recreate,
            }
        )

    @cached_property
    def chat_with_assistant_use_case(self) -> ChatWithAssistantUseCase:
        return ChatWithAssistantUseCase(self.chat_orchestrator)
