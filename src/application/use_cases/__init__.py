"""Use cases (regras de aplicação) do crítico jurídico."""

from src.application.use_cases.analyze_petition import AnalyzePetitionUseCase
from src.application.use_cases.build_index import BuildIndexUseCase, LoadOrBuildIndexUseCase
from src.application.use_cases.chat_with_assistant import ChatWithAssistantUseCase
from src.application.use_cases.download_petitions import DownloadPetitionsUseCase
from src.application.use_cases.generate_corpus_report import GenerateCorpusReportUseCase
from src.application.use_cases.recreate_petition import RecreatePetitionUseCase

__all__ = [
    "AnalyzePetitionUseCase",
    "BuildIndexUseCase",
    "ChatWithAssistantUseCase",
    "DownloadPetitionsUseCase",
    "GenerateCorpusReportUseCase",
    "LoadOrBuildIndexUseCase",
    "RecreatePetitionUseCase",
]
