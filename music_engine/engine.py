"""Music & Audio Mixing Engine facade (Phase C8).

The high-level, reusable API: turn intent (or explicit specs) into a validated,
Timeline-native :class:`MusicTrack`. It wires three pieces —

    planner (scene-aware timing)  ->  provider (local file / procedural bed)
                                  ->  builder (apply config, fill defaults)

— and nothing else. It produces *data* (a music track); the actual mixing is a
render concern (the renderer lowers the track by mixing audio under the voice via
the shared deterministic mixer). No AI music generation, no streaming, no
licensing, no beat detection — Phase C8 is purely deterministic mixing.
"""
from __future__ import annotations

from pathlib import Path

from foundation.logging import get_logger
from reel_engine.interfaces.types import MusicTrack, Timeline

from music_engine.config.settings import MusicEngineConfig, load_music_engine_config
from music_engine.mixing.planner import plan_background_music, plan_for_timeline
from music_engine.providers.base import LocalMusicProvider, MusicProvider, MusicSpec
from music_engine.timeline.builder import build_music_track

logger = get_logger("music_engine")


class MusicEngine:
    """Intent/specs -> a validated, Timeline-native MusicTrack (deterministic)."""

    def __init__(
        self,
        config: MusicEngineConfig | None = None,
        *,
        provider: MusicProvider | None = None,
    ) -> None:
        self.config = config or load_music_engine_config()
        self.provider = provider or LocalMusicProvider()

    def build(
        self,
        specs: list[MusicSpec],
        reel_duration_s: float,
        *,
        sample_rate: int = 44_100,
        asset_dir: Path | str | None = None,
        track_id: str = "music",
    ) -> MusicTrack:
        """Resolve and assemble a :class:`MusicTrack` from explicit specs."""
        track = build_music_track(
            specs, reel_duration_s, config=self.config, provider=self.provider,
            sample_rate=sample_rate,
            asset_dir=Path(asset_dir) if asset_dir is not None else None,
            track_id=track_id)
        self._log(track)
        return track

    def generate(
        self,
        reel_duration_s: float,
        *,
        soundtrack: str | None = None,
        source: str | None = None,
        gain: float | None = None,
        duck: bool | None = None,
        mute_sections: tuple = (),
        sample_rate: int = 44_100,
        asset_dir: Path | str | None = None,
        track_id: str = "music",
    ) -> MusicTrack:
        """One whole-reel background bed from config defaults (the common case).

        Pick a built-in ``soundtrack`` name or supply a local ``source`` file; with
        neither, the config's ``default_soundtrack`` is used. Fades, loop, and
        ducking all come from the engine config."""
        spec = plan_background_music(
            reel_duration_s, self.config, soundtrack=soundtrack, source=source,
            gain=gain, duck=duck, mute_sections=mute_sections)
        return self.build([spec], reel_duration_s, sample_rate=sample_rate,
                          asset_dir=asset_dir, track_id=track_id)

    def generate_for_timeline(
        self,
        timeline: Timeline,
        *,
        soundtrack: str | None = None,
        source: str | None = None,
        gain: float | None = None,
        duck: bool | None = None,
        sample_rate: int = 44_100,
        asset_dir: Path | str | None = None,
        track_id: str = "music",
    ) -> MusicTrack:
        """Scene-aware bed: fades matched to the timeline's branding intro/outro."""
        spec = plan_for_timeline(timeline, self.config, soundtrack=soundtrack,
                                 source=source, gain=gain, duck=duck)
        return self.build([spec], timeline.duration_s, sample_rate=sample_rate,
                          asset_dir=asset_dir, track_id=track_id)

    def _log(self, track: MusicTrack) -> None:
        logger.info("Music track built", extra={"context": {
            "clips": track.n_clips, "gain": track.gain,
            "sources": [c.source.meta.get("music_source") if c.source else None
                        for c in track.clips],
            "ducking": [c.ducking.enabled for c in track.clips]}})
