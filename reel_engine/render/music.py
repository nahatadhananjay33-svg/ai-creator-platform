"""Music lowering & mixing (Phase C8) — ``MusicTrack`` → one mixed audio bed.

The renderer must *consume* music tracks, never hardcode a soundtrack: this
module is the single place that turns declarative :class:`MusicClip` data into
concrete audio samples and mixes them **under the voice**. Both backends (the
hermetic mock proxy and the real FFmpeg MP4) mix with the SAME code, so the
audio is byte-identical across renderers and fully deterministic.

The mix is built in the normalized float domain via
:mod:`foundation.shared_utils.audio_mix`:

    voice bed (from the scenes' real audio)                      ─┐
    each music clip: load → loop → fade → envelope → duck → mute ─┤ sum
                                                                  ─┘ → soft-limit → int16

Ducking is driven by the reel's **speech windows** (caption segments, else the
spoken scenes) — the plan, not the waveform — so it is deterministic and
identical everywhere. The soft limiter guarantees the result can never clip.
Pure apart from reading the (local) source WAVs; no network, no model.
"""
from __future__ import annotations

from foundation.shared_utils import WavData, read_wav
from foundation.shared_utils.audio_mix import (
    apply_fades,
    apply_gains,
    apply_mute_sections,
    envelope_gains,
    ducking_gains,
    mix_into,
    peak,
    resample_nearest,
    soft_limit,
    tile_to_length,
    to_float,
    to_int16,
)
from reel_engine.interfaces.types import MusicClip, Timeline

#: Fallback sample rate when a caller does not pass one (matches the render
#: config default). The renderer always passes its own ``audio_sample_rate``.
DEFAULT_SAMPLE_RATE = 44_100


def has_music(timeline: Timeline) -> bool:
    """True if the timeline carries at least one music clip to mix."""
    return timeline.has_music


def resolve_music(timeline: Timeline) -> list[tuple]:
    """Every ``(clip, track_gain)`` across all music tracks, in start order.

    The track master gain travels with each clip so the mixer applies it without
    re-reading the track. Sorted by ``start_s`` for stable, deterministic mixing."""
    pairs: list[tuple] = [
        (clip, track.gain) for track in timeline.music_tracks for clip in track.clips
    ]
    pairs.sort(key=lambda cg: cg[0].start_s)
    return pairs


def speech_windows(timeline: Timeline) -> list[tuple]:
    """Absolute ``(start_s, end_s)`` spans where narration is present.

    Prefers the caption segments (they ARE the narration windows); falls back to
    the spoken scenes (those carrying a real audio file) laid end to end. Empty
    when the reel has neither — ducking then has nothing to duck against."""
    windows: list[tuple] = []
    for track in timeline.caption_tracks:
        for seg in track.segments:
            windows.append((seg.start_s, seg.end_s))
    if windows:
        windows.sort()
        return windows
    cursor = 0.0
    for scene in timeline.scenes:
        if scene.audio_file_clip() is not None:
            windows.append((cursor, cursor + scene.duration_s))
        cursor += scene.duration_s
    return windows


def build_voice_bed(timeline: Timeline, sr: int, n_total: int) -> list[float]:
    """The reel's voice as a float buffer of ``n_total`` samples at ``sr``.

    Sums each scene's real audio file (the authoritative Voice Engine WAV) at its
    cumulative scene offset, resampling to ``sr``. Scenes with only a silent bed
    contribute nothing. Returns all-zeros when the reel has no real audio (e.g.
    the hermetic mock path) — the music still mixes and ducks, just over silence."""
    bed = [0.0] * n_total
    cursor = 0.0
    for scene in timeline.scenes:
        aclip = scene.audio_file_clip()
        if aclip is not None and aclip.source is not None:
            wav = read_wav(aclip.source.uri)
            samples = resample_nearest(to_float(wav.samples), wav.sample_rate, sr)
            mix_into(bed, samples, int(round(cursor * sr)))
        cursor += scene.duration_s
    return bed


def _render_music_clip(clip: MusicClip, track_gain: float, sr: int,
                       windows: list[tuple]) -> tuple:
    """Return ``(samples, offset_n)`` for one fully-processed music clip.

    Loads the source, loops it to the clip window, then applies (all multiplicative,
    so order-independent): base gain, fades, the volume envelope, ducking, and any
    mute sections. ``offset_n`` is where the clip sits in the reel (samples)."""
    n_win = max(0, int(round(clip.duration_s * sr)))
    if n_win == 0:
        return [], 0
    wav = read_wav(clip.source.uri)
    src = resample_nearest(to_float(wav.samples), wav.sample_rate, sr)
    off = int(round(clip.source_offset_s * sr))
    if off:
        src = src[off:]

    if clip.loop.enabled:
        xf = int(round(clip.loop.crossfade_s * sr))
        samples = tile_to_length(src, n_win, crossfade_n=xf)
    else:                                       # play once, pad the remainder
        samples = (src[:n_win] + [0.0] * n_win)[:n_win]

    g = clip.gain * track_gain
    samples = [s * g for s in samples]
    apply_fades(samples, sr, clip.fade.fade_in_s, clip.fade.fade_out_s)
    if not clip.envelope.is_empty:
        apply_gains(samples, envelope_gains(clip.envelope.points, sr, n_win,
                                            offset_s=clip.start_s))
    if clip.ducking.enabled and windows:
        apply_gains(samples, ducking_gains(
            n_win, sr, windows, duck_level=clip.ducking.duck_level,
            attack_s=clip.ducking.attack_s, release_s=clip.ducking.release_s,
            pad_s=clip.ducking.pad_s, offset_s=clip.start_s))
    if clip.mute_sections:
        apply_mute_sections(samples, sr, clip.mute_sections, offset_s=clip.start_s)
    return samples, int(round(clip.start_s * sr))


def mix_timeline_audio(timeline: Timeline, sr: int | None = None, *,
                       voice: list[float] | None = None) -> WavData:
    """Mix the reel's voice + every music clip into one 16-bit PCM :class:`WavData`.

    ``sr`` defaults to :data:`DEFAULT_SAMPLE_RATE`. The voice bed is taken from the
    scenes' real audio (override with ``voice`` for an explicit bed). Music is
    summed on top and the whole mix is soft-limited so it can never clip. When the
    timeline has no music this is just the voice bed (or silence) — a safe no-op."""
    sr = sr or DEFAULT_SAMPLE_RATE
    n_total = max(1, int(round(timeline.duration_s * sr)))
    mix = list(voice) if voice is not None else build_voice_bed(timeline, sr, n_total)
    if len(mix) < n_total:
        mix.extend([0.0] * (n_total - len(mix)))

    windows = speech_windows(timeline)
    for clip, track_gain in resolve_music(timeline):
        samples, offset_n = _render_music_clip(clip, track_gain, sr, windows)
        mix_into(mix, samples, offset_n)

    soft_limit(mix)
    return WavData(samples=to_int16(mix), sample_rate=sr, channels=1)


def mixed_peak(timeline: Timeline, sr: int | None = None) -> float:
    """Peak absolute amplitude (0..1) of the mixed reel — a cheap clipping check."""
    wav = mix_timeline_audio(timeline, sr)
    return peak(to_float(wav.samples))
