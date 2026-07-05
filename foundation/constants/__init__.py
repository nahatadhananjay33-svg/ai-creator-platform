"""Platform-wide constants: paths, languages, audio parameters."""

from foundation.constants.audio import AudioFormat, DEFAULT_SAMPLE_RATE, TELEPHONY_SAMPLE_RATE
from foundation.constants.languages import Language, LanguageInfo, LANGUAGE_INFO
from foundation.constants.paths import (
    PROJECT_ROOT,
    FOUNDATION_DIR,
    VOICE_ENGINE_DIR,
    CACHE_DIR,
    ensure_dir,
)

__all__ = [
    "AudioFormat",
    "DEFAULT_SAMPLE_RATE",
    "TELEPHONY_SAMPLE_RATE",
    "Language",
    "LanguageInfo",
    "LANGUAGE_INFO",
    "PROJECT_ROOT",
    "FOUNDATION_DIR",
    "VOICE_ENGINE_DIR",
    "CACHE_DIR",
    "ensure_dir",
]
