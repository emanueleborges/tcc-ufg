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
from src.application.use_cases.application_evaluations import (
    DeleteAnalyzedPetitionUseCase,
    ListApplicationEvaluationsUseCase,
    ListEvaluatorsUseCase,
)
from src.application.use_cases.validation_metrics import GetValidationMetricsUseCase
from src.application.use_cases.submit_human_validation import (
    DeleteHumanValidationUseCase,
    GetCampaignProgressUseCase,
    GetHumanValidationUseCase,
    ListHumanValidationsUseCase,
    SubmitHumanValidationUseCase,
)

__all__ = [
    "AnalyzePetitionUseCase",
    "BuildIndexUseCase",
    "ChatWithAssistantUseCase",
    "DeleteAnalyzedPetitionUseCase",
    "DeleteReadingTimeUseCase",
    "DownloadPetitionsUseCase",
    "DeleteHumanValidationUseCase",
    "GenerateCorpusReportUseCase",
    "GetCampaignProgressUseCase",
    "GetHumanValidationUseCase",
    "GetValidationMetricsUseCase",
    "ListAnalysisTimesUseCase",
    "ListApplicationEvaluationsUseCase",
    "ListEvaluatorsUseCase",
    "ListHumanValidationsUseCase",
    "ListReadingTimesUseCase",
    "LoadOrBuildIndexUseCase",
    "MeasureAnalysisTimeUseCase",
    "SubmitHumanValidationUseCase",
    "SubmitReadingTimeUseCase",
    "UpdateReadingTimeUseCase",
]
