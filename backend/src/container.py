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
    DeleteReadingTimeUseCase,
    ChatWithAssistantUseCase,
    DownloadPetitionsUseCase,
    GenerateCorpusReportUseCase,
    GetHumanValidationUseCase,
    GetValidationMetricsUseCase,
    ListAnalysisTimesUseCase,
    ListHumanValidationsUseCase,
    ListReadingTimesUseCase,
    LoadOrBuildIndexUseCase,
    MeasureAnalysisTimeUseCase,
    SubmitHumanValidationUseCase,
    SubmitReadingTimeUseCase,
    UpdateReadingTimeUseCase,
)
from src.config.settings import Settings, get_settings
from src.domain.chat import Intent
from src.infrastructure.langchain.ollama_chat import LangChainOllamaChat
from src.infrastructure.nlp.embedding_engine import SentenceTransformerEmbeddingEngine
from src.infrastructure.pdf.pdf_reader import PdfReader
from src.infrastructure.pdf.pdf_writer import ReportlabPdfWriter
from src.infrastructure.persistence.chroma_index_repository import ChromaIndexRepository
from src.infrastructure.persistence.analysis_time_repository_sqlite import (
    SQLiteAnalysisTimeRepository,
)
from src.infrastructure.persistence.reading_time_repository_sqlite import (
    SQLiteReadingTimeRepository,
)
from src.infrastructure.persistence.validation_repository_sqlite import (
    DB_FILE_NAME as VALIDATION_DB_FILE,
    SQLiteValidationRepository,
)
from src.infrastructure.scraping.pdf_scraper import PdfScraper
from src.infrastructure.search.duckduckgo_search import DuckDuckGoWebSearch
from src.services.chat.internet_answerer import InternetAnswerer
from src.services.chat.ollama_answerer import OllamaAnswerer
from src.services.chat.orchestrator import ChatOrchestrator
from src.services.chat.petition_answerers import AnalyzePetitionAnswerer
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
    def index_repository(self) -> ChromaIndexRepository:
        return ChromaIndexRepository(self.settings.paths.index_dir)

    @cached_property
    def validation_repository(self) -> SQLiteValidationRepository:
        return SQLiteValidationRepository(
            self.settings.paths.validations_dir / VALIDATION_DB_FILE,
            legacy_dir=self.settings.paths.validations_dir,
        )

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
    def analysis_time_repository(self) -> SQLiteAnalysisTimeRepository:
        return SQLiteAnalysisTimeRepository(
            self.settings.paths.validations_dir / VALIDATION_DB_FILE
        )

    @cached_property
    def analyze_petition_use_case(self) -> AnalyzePetitionUseCase:
        return AnalyzePetitionUseCase(
            chunk_factory=self.chunk_factory,
            semantic_search=self.semantic_search,
            rag_settings=self.settings.rag,
            analysis_time_repository=self.analysis_time_repository,
        )

    @cached_property
    def download_petitions_use_case(self) -> DownloadPetitionsUseCase:
        return DownloadPetitionsUseCase(self.pdf_scraper)

    @cached_property
    def generate_corpus_report_use_case(self) -> GenerateCorpusReportUseCase:
        return GenerateCorpusReportUseCase(self.settings.paths)

    @cached_property
    def submit_human_validation_use_case(self) -> SubmitHumanValidationUseCase:
        return SubmitHumanValidationUseCase(self.validation_repository)

    @cached_property
    def list_human_validations_use_case(self) -> ListHumanValidationsUseCase:
        return ListHumanValidationsUseCase(self.validation_repository)

    @cached_property
    def get_human_validation_use_case(self) -> GetHumanValidationUseCase:
        return GetHumanValidationUseCase(self.validation_repository)

    @cached_property
    def get_validation_metrics_use_case(self) -> GetValidationMetricsUseCase:
        return GetValidationMetricsUseCase(self.validation_repository)

    @cached_property
    def reading_time_repository(self) -> SQLiteReadingTimeRepository:
        return SQLiteReadingTimeRepository(
            self.settings.paths.validations_dir / VALIDATION_DB_FILE
        )

    @cached_property
    def submit_reading_time_use_case(self) -> SubmitReadingTimeUseCase:
        return SubmitReadingTimeUseCase(self.reading_time_repository)

    @cached_property
    def list_reading_times_use_case(self) -> ListReadingTimesUseCase:
        return ListReadingTimesUseCase(
            self.reading_time_repository,
            analysis_repository=self.analysis_time_repository,
        )

    @cached_property
    def list_analysis_times_use_case(self) -> ListAnalysisTimesUseCase:
        return ListAnalysisTimesUseCase(self.analysis_time_repository)

    @cached_property
    def measure_analysis_time_use_case(self) -> MeasureAnalysisTimeUseCase:
        return MeasureAnalysisTimeUseCase(
            analyze=self.analyze_petition_use_case,
            repository=self.analysis_time_repository,
            uploads_dir=self.settings.paths.uploads_dir,
        )

    @cached_property
    def update_reading_time_use_case(self) -> UpdateReadingTimeUseCase:
        return UpdateReadingTimeUseCase(self.reading_time_repository)

    @cached_property
    def delete_reading_time_use_case(self) -> DeleteReadingTimeUseCase:
        return DeleteReadingTimeUseCase(self.reading_time_repository)

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
        return ChatOrchestrator(
            {
                Intent.ASK_OLLAMA: ollama,
                Intent.ASK_RAG: rag,
                Intent.ASK_INTERNET: internet,
                Intent.ANALYZE_PETITION: analyze,
            }
        )

    @cached_property
    def chat_with_assistant_use_case(self) -> ChatWithAssistantUseCase:
        return ChatWithAssistantUseCase(self.chat_orchestrator)
