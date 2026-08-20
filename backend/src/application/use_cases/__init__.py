"""Use cases (regras de aplicação) do crítico jurídico."""

from src.application.use_cases.analyze_petition import AnalyzePetitionUseCase
from src.application.use_cases.build_index import BuildIndexUseCase, LoadOrBuildIndexUseCase
from src.application.use_cases.chat_with_assistant import ChatWithAssistantUseCase
from src.application.use_cases.download_petitions import DownloadPetitionsUseCase
from src.application.use_cases.generate_corpus_report import GenerateCorpusReportUseCase
from src.application.use_cases.analysis_times import (
    ListAnalysisTimesUseCase,
    MeasureAnalysisTimeUseCase,
)
from src.application.use_cases.reading_times import (
    DeleteReadingTimeUseCase,
    ListReadingTimesUseCase,
    SubmitReadingTimeUseCase,
    UpdateReadingTimeUseCase,
)
from src.application.use_cases.submit_human_validation import (
    GetHumanValidationUseCase,
    ListHumanValidationsUseCase,
    SubmitHumanValidationUseCase,
)
from src.application.use_cases.validation_metrics import GetValidationMetricsUseCase

__all__ = [
    "AnalyzePetitionUseCase",
    "BuildIndexUseCase",
    "ChatWithAssistantUseCase",
    "DeleteReadingTimeUseCase",
    "DownloadPetitionsUseCase",
    "GenerateCorpusReportUseCase",
    "GetHumanValidationUseCase",
    "GetValidationMetricsUseCase",
    "ListAnalysisTimesUseCase",
    "ListHumanValidationsUseCase",
    "ListReadingTimesUseCase",
    "LoadOrBuildIndexUseCase",
    "MeasureAnalysisTimeUseCase",
    "SubmitHumanValidationUseCase",
    "SubmitReadingTimeUseCase",
    "UpdateReadingTimeUseCase",
]
