"""Persistent voice-profile store.

Profiles live as one directory per profile under a gitignored root
(``voice_engine/voices/profiles/`` by default):

    profiles/<profile_id>/profile.json   # serialized VoiceProfile
    profiles/<profile_id>/reference.wav  # durable copy of the reference clip

Consent metadata is mandatory by default: a cloned voice may not enter the
production library without a recorded consent statement (who consented,
when, for what use). Set ``require_consent=False`` only for throwaway
development stores.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from foundation.constants import VOICE_ENGINE_DIR, Language, ensure_dir
from foundation.exceptions import PlatformError
from foundation.logging import get_logger
from foundation.shared_utils.timing import utc_now_iso
from voice_engine.interfaces import VoiceProfile

logger = get_logger("voice_engine.voices")

DEFAULT_PROFILES_DIR: Path = VOICE_ENGINE_DIR / "voices" / "profiles"

_PROFILE_FILE = "profile.json"
_REFERENCE_FILE = "reference.wav"

CONSENT_KEY = "consent"


class ProfileNotFoundError(PlatformError):
    """Requested voice profile does not exist in the store."""


class ConsentMissingError(PlatformError):
    """Profile lacks the mandatory consent metadata."""


def profile_to_dict(profile: VoiceProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "engine_id": profile.engine_id,
        "display_name": profile.display_name,
        "reference_audio": str(profile.reference_audio) if profile.reference_audio else None,
        "language_hint": profile.language_hint.value if profile.language_hint else None,
        "artifacts": dict(profile.artifacts),
        "metadata": dict(profile.metadata),
    }


def profile_from_dict(data: dict[str, Any]) -> VoiceProfile:
    return VoiceProfile(
        profile_id=data["profile_id"],
        engine_id=data["engine_id"],
        display_name=data["display_name"],
        reference_audio=Path(data["reference_audio"]) if data.get("reference_audio") else None,
        language_hint=Language.from_code(data["language_hint"]) if data.get("language_hint") else None,
        artifacts=dict(data.get("artifacts", {})),
        metadata=dict(data.get("metadata", {})),
    )


class VoiceProfileManager:
    """CRUD store for :class:`VoiceProfile` objects."""

    def __init__(
        self,
        directory: Path | str | None = None,
        require_consent: bool = True,
    ) -> None:
        self.directory = ensure_dir(Path(directory) if directory else DEFAULT_PROFILES_DIR)
        self.require_consent = require_consent

    def _profile_dir(self, profile_id: str) -> Path:
        if not profile_id or any(sep in profile_id for sep in ("/", "\\", "..")):
            raise PlatformError(f"Invalid profile id: {profile_id!r}")
        return self.directory / profile_id

    # ------------------------------------------------------------------ CRUD
    def save(self, profile: VoiceProfile, copy_reference: bool = True) -> VoiceProfile:
        """Persist a profile (idempotent overwrite by ``profile_id``).

        The reference clip is copied into the store so profiles survive the
        original upload location disappearing.

        Raises:
            ConsentMissingError: consent metadata absent and this store
                requires it.
        """
        if self.require_consent and not profile.metadata.get(CONSENT_KEY):
            raise ConsentMissingError(
                "Voice profile has no consent metadata; record who consented, "
                f"when, and for what use under metadata[{CONSENT_KEY!r}]",
                profile_id=profile.profile_id,
            )
        profile_dir = ensure_dir(self._profile_dir(profile.profile_id))
        stored = profile
        if copy_reference and profile.reference_audio is not None:
            stored_ref = profile_dir / _REFERENCE_FILE
            if profile.reference_audio.resolve() != stored_ref.resolve():
                shutil.copyfile(profile.reference_audio, stored_ref)
            stored = replace(profile, reference_audio=stored_ref)
        payload = profile_to_dict(stored)
        payload["saved_at"] = utc_now_iso()
        tmp = profile_dir / f"{_PROFILE_FILE}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(profile_dir / _PROFILE_FILE)
        logger.info(
            "Voice profile saved",
            extra={"context": {"profile_id": stored.profile_id, "engine": stored.engine_id}},
        )
        return stored

    def load(self, profile_id: str) -> VoiceProfile:
        path = self._profile_dir(profile_id) / _PROFILE_FILE
        if not path.exists():
            raise ProfileNotFoundError(
                f"Voice profile not found: {profile_id!r}",
                profile_id=profile_id,
                known=self.list_ids(),
            )
        return profile_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def exists(self, profile_id: str) -> bool:
        return (self._profile_dir(profile_id) / _PROFILE_FILE).exists()

    def list_ids(self) -> list[str]:
        return sorted(
            entry.name
            for entry in self.directory.iterdir()
            if (entry / _PROFILE_FILE).exists()
        )

    def list_profiles(self, engine_id: str | None = None) -> list[VoiceProfile]:
        profiles = (self.load(pid) for pid in self.list_ids())
        if engine_id is None:
            return list(profiles)
        return [p for p in profiles if p.engine_id == engine_id]

    def delete(self, profile_id: str) -> bool:
        profile_dir = self._profile_dir(profile_id)
        if not profile_dir.exists():
            return False
        shutil.rmtree(profile_dir)
        logger.info("Voice profile deleted", extra={"context": {"profile_id": profile_id}})
        return True
