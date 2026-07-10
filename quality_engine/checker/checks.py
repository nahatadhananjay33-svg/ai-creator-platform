"""The deterministic reel checks (Phase C16).

Each check is a pure function ``(artifacts, inspection, config) -> CheckResult`` —
a fixed rule over already-measured facts, no AI/ML, no side effects. They split
into two intents:

- **required** (a violation is a ``FAIL`` that fails the gate): the master exists,
  it is playable, it carries audio whose length matches the video, the resolution
  is correct, and the reel length is within the configured limits.
- **advisory** (absence is a ``WARN`` that never fails the gate): the optional
  creative elements — avatar, voice, captions, branding, music — so a minimal but
  valid reel still passes while missing pieces are surfaced.

Content presence (captions / branding / music) is read from the declarative
:class:`~reel_engine.interfaces.types.Timeline`, so it is identical for the mock
and ffmpeg backends; when no Timeline is supplied the checks fall back to the
sidecars they can see (or ``SKIP`` when they can see nothing).
"""
from __future__ import annotations

from pathlib import Path

from reel_engine.interfaces.types import aspect_ratio_string

from quality_engine.checker.config import QualityConfig
from quality_engine.checker.model import ReelArtifacts, ReelInspection
from quality_engine.checker.report import CheckResult, CheckStatus

PASS, WARN, FAIL, SKIP = (CheckStatus.PASS, CheckStatus.WARN,
                          CheckStatus.FAIL, CheckStatus.SKIP)


def _r(key: str, label: str, status: CheckStatus, detail: str = "") -> CheckResult:
    return CheckResult(key=key, label=label, status=status, detail=detail)


# --------------------------------------------------------------- required checks
def check_video_exists(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    if insp.master_exists:
        return _r("video_exists", "Video file exists", PASS, str(a.master_path))
    return _r("video_exists", "Video file exists", FAIL, f"missing: {a.master_path}")


def check_video_playable(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    if not insp.master_exists:
        return _r("video_playable", "Video playable", SKIP, "no master to probe")
    if insp.video_readable and insp.n_frames > 0:
        return _r("video_playable", "Video playable", PASS,
                  f"{insp.width}x{insp.height} {insp.fps:g}fps, {insp.n_frames} frames")
    detail = "; ".join(insp.errors) or "no decodable video frames"
    return _r("video_playable", "Video playable", FAIL, detail)


def check_audio_exists(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    if insp.audio_present:
        return _r("audio_exists", "Audio detected", PASS, f"source={insp.audio_source}")
    return _r("audio_exists", "Audio detected", FAIL, "no audio stream or sidecar")


def check_audio_matches_video(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Audio duration matches video"
    if not insp.audio_present:
        return _r("audio_matches_video", label, SKIP, "no audio")
    if insp.audio_source == "muxed":  # single container timeline => aligned by construction
        return _r("audio_matches_video", label, PASS, "muxed with video")
    if insp.audio_duration_s is None:
        return _r("audio_matches_video", label, SKIP, "audio duration unknown")
    delta = abs(insp.audio_duration_s - insp.video_duration_s)
    detail = (f"audio={insp.audio_duration_s:.3f}s video={insp.video_duration_s:.3f}s "
              f"(|Δ|={delta:.3f}s, tol={c.audio_sync_tolerance_s:g}s)")
    status = PASS if delta <= c.audio_sync_tolerance_s else FAIL
    return _r("audio_matches_video", label, status, detail)


def check_resolution_correct(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Export resolution correct"
    problems: list[str] = []
    checked = False

    # master: exact dims if pinned, else aspect vs the Timeline
    if insp.master_exists and insp.video_readable:
        if c.expected_width and c.expected_height:
            checked = True
            if (insp.width, insp.height) != (c.expected_width, c.expected_height):
                problems.append(f"master {insp.width}x{insp.height} != "
                                f"{c.expected_width}x{c.expected_height}")
        elif a.timeline is not None:
            checked = True
            want = a.timeline.meta.aspect
            got = aspect_ratio_string(insp.width, insp.height)
            if got != want:
                problems.append(f"master aspect {got} != {want}")

    # exports: aspect must match the profile each claims
    for ep in insp.exports:
        checked = True
        if not ep.exists:
            problems.append(f"export {ep.profile} missing")
        elif not ep.aspect_ok:
            problems.append(f"export {ep.profile} aspect {ep.aspect} != {ep.expected_aspect}")

    if not checked:
        return _r("resolution_correct", label, SKIP, "nothing to verify")
    if problems:
        return _r("resolution_correct", label, FAIL, "; ".join(problems))
    n = len(insp.exports)
    return _r("resolution_correct", label, PASS,
              f"{insp.width}x{insp.height} + {n} export(s)")


def check_duration_within_limits(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Duration within limits"
    if not (insp.master_exists and insp.video_readable):
        return _r("duration_within_limits", label, SKIP, "no readable video")
    d = insp.video_duration_s
    detail = f"{d:.3f}s (limits {c.min_duration_s:g}-{c.max_duration_s:g}s)"
    ok = c.min_duration_s <= d <= c.max_duration_s
    return _r("duration_within_limits", label, PASS if ok else FAIL, detail)


# --------------------------------------------------------------- advisory checks
def check_avatar_present(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Avatar present"
    plan = a.avatar
    if not plan:
        return _r("avatar_present", label, WARN, "no avatar plan")
    if not plan.get("enabled", False):
        return _r("avatar_present", label, WARN, "avatar disabled")
    n = len(plan.get("clips", []) or [])
    if n == 0:
        return _r("avatar_present", label, WARN, "avatar plan has no clips")
    return _r("avatar_present", label, PASS, f"{n} clip(s) planned")


def check_voice_present(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Voice present"
    clips = [Path(p) for p in a.voice_clips]
    if clips and all(p.exists() for p in clips):
        return _r("voice_present", label, PASS, f"{len(clips)} narration clip(s)")
    if insp.audio_present and not insp.audio_silent:
        return _r("voice_present", label, PASS, "non-silent audio present")
    if insp.audio_present and insp.audio_silent:
        return _r("voice_present", label, WARN, "audio is silent (no narration)")
    return _r("voice_present", label, WARN, "no voice clips or audio")


def check_captions_present(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Captions generated"
    if a.timeline is not None:
        if a.timeline.has_captions:
            return _r("captions_present", label, PASS, "caption track in timeline")
        if insp.captions_sidecar_exists and insp.n_caption_cues > 0:
            return _r("captions_present", label, PASS,
                      f"{insp.n_caption_cues} sidecar cue(s)")
        return _r("captions_present", label, WARN, "no captions")
    if insp.captions_sidecar_exists and insp.n_caption_cues > 0:
        return _r("captions_present", label, PASS, f"{insp.n_caption_cues} sidecar cue(s)")
    return _r("captions_present", label, WARN, "no caption sidecar")


def check_branding_present(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Branding present"
    if a.timeline is None:
        return _r("branding_present", label, SKIP, "no timeline to inspect")
    if a.timeline.has_branding:
        return _r("branding_present", label, PASS, "branding elements in timeline")
    return _r("branding_present", label, WARN, "no branding")


def check_music_present(a: ReelArtifacts, insp: ReelInspection, c: QualityConfig) -> CheckResult:
    label = "Music present"
    if a.timeline is None:
        return _r("music_present", label, SKIP, "no timeline to inspect")
    if a.timeline.has_music:
        return _r("music_present", label, PASS, "music bed in timeline")
    return _r("music_present", label, WARN, "no music")


#: The checks in report order. Required checks first (they gate), then advisory.
CHECKS = (
    check_video_exists,
    check_video_playable,
    check_audio_exists,
    check_audio_matches_video,
    check_avatar_present,
    check_voice_present,
    check_captions_present,
    check_branding_present,
    check_music_present,
    check_resolution_correct,
    check_duration_within_limits,
)


def run_checks(artifacts: ReelArtifacts, inspection: ReelInspection,
               config: QualityConfig) -> tuple[CheckResult, ...]:
    """Run every check in report order and return their results."""
    return tuple(fn(artifacts, inspection, config) for fn in CHECKS)
