"""Tests for the persistent voice-profile store."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.shared_utils import generate_sine_wav, write_wav
from voice_engine.interfaces import VoiceProfile
from voice_engine.voices import (
    CONSENT_KEY,
    ConsentMissingError,
    ProfileNotFoundError,
    VoiceProfileManager,
    profile_from_dict,
    profile_to_dict,
)


@pytest.fixture()
def manager(tmp_path: Path) -> VoiceProfileManager:
    return VoiceProfileManager(directory=tmp_path / "profiles")


@pytest.fixture()
def profile(tmp_path: Path) -> VoiceProfile:
    ref = write_wav(tmp_path / "ref.wav", generate_sine_wav(duration_s=5.0))
    return VoiceProfile(
        profile_id="mock-abc123",
        engine_id="mock",
        display_name="Agent Priya",
        reference_audio=ref,
        language_hint=Language.HINDI,
        metadata={CONSENT_KEY: "P. Sharma, 2026-07-04, marketing use"},
    )


def test_save_load_roundtrip(manager: VoiceProfileManager, profile: VoiceProfile) -> None:
    stored = manager.save(profile)
    loaded = manager.load(profile.profile_id)
    assert loaded.profile_id == profile.profile_id
    assert loaded.display_name == "Agent Priya"
    assert loaded.language_hint is Language.HINDI
    assert loaded.metadata[CONSENT_KEY].startswith("P. Sharma")
    # Reference clip is copied into the store for durability.
    assert loaded.reference_audio == stored.reference_audio
    assert loaded.reference_audio is not None and loaded.reference_audio.exists()
    assert loaded.reference_audio.parent == manager.directory / profile.profile_id


def test_consent_is_mandatory_by_default(
    manager: VoiceProfileManager, profile: VoiceProfile
) -> None:
    no_consent = VoiceProfile(
        profile_id="mock-noconsent",
        engine_id="mock",
        display_name="Anonymous",
        reference_audio=profile.reference_audio,
    )
    with pytest.raises(ConsentMissingError):
        manager.save(no_consent)
    relaxed = VoiceProfileManager(directory=manager.directory, require_consent=False)
    relaxed.save(no_consent)  # dev stores may opt out
    assert relaxed.exists("mock-noconsent")


def test_list_filter_and_delete(manager: VoiceProfileManager, profile: VoiceProfile) -> None:
    manager.save(profile)
    assert manager.list_ids() == [profile.profile_id]
    assert manager.list_profiles(engine_id="mock")[0].engine_id == "mock"
    assert manager.list_profiles(engine_id="kokoro") == []
    assert manager.delete(profile.profile_id) is True
    assert manager.delete(profile.profile_id) is False
    assert manager.list_ids() == []


def test_load_missing_profile_raises(manager: VoiceProfileManager) -> None:
    with pytest.raises(ProfileNotFoundError):
        manager.load("nope")


def test_serialization_roundtrip(profile: VoiceProfile) -> None:
    restored = profile_from_dict(profile_to_dict(profile))
    assert restored == profile


def test_invalid_profile_id_rejected(manager: VoiceProfileManager) -> None:
    from foundation.exceptions import PlatformError

    with pytest.raises(PlatformError):
        manager.load("../escape")
