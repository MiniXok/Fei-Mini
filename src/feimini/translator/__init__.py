"""自然语言翻译与端到端 SQLite 助理模块。"""

from .contract import (
    AggregationIntent,
    FilterIntent,
    SortIntent,
    IntentSpec,
    validate_intent_against_schema,
)
from .resolver import IntentResolver, IntentResolutionError
from .client import LocalTranslatorClient, TranslatorClientError, TranslatorTimeoutError
from .pipeline import NaturalLanguageSQLiteAssistant, NaturalLanguageQueryResult

__all__ = [
    "AggregationIntent",
    "FilterIntent",
    "SortIntent",
    "IntentSpec",
    "validate_intent_against_schema",
    "IntentResolver",
    "IntentResolutionError",
    "LocalTranslatorClient",
    "TranslatorClientError",
    "TranslatorTimeoutError",
    "NaturalLanguageSQLiteAssistant",
    "NaturalLanguageQueryResult",
]
