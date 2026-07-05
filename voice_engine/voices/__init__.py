"""Voice library: persistent registry of production voice profiles.

Cloned profiles carry mandatory consent metadata; storage under
``profiles/`` is gitignored.
"""

from voice_engine.voices.profile_manager import (
    CONSENT_KEY,
    DEFAULT_PROFILES_DIR,
    ConsentMissingError,
    ProfileNotFoundError,
    VoiceProfileManager,
    profile_from_dict,
    profile_to_dict,
)

__all__ = [
    "CONSENT_KEY",
    "DEFAULT_PROFILES_DIR",
    "ConsentMissingError",
    "ProfileNotFoundError",
    "VoiceProfileManager",
    "profile_from_dict",
    "profile_to_dict",
]
