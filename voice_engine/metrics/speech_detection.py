"""Classify a WAV as real speech, placeholder tone, silence, or corrupted.

Phase A3.8.5. The avatar benchmark's driving audio is meant to be real Kokoro
speech; when audio is missing the framework can substitute a **220 Hz sine
placeholder** (``datasets.manager.generate_placeholder_assets``). Driving
SadTalker with a constant tone produces meaningless lip-sync, so this module
lets the benchmark *verify* the audio before generation instead of silently
proceeding.

Stdlib only (``array``/``math`` + ``wave`` via ``read_wav``) so it runs in the
benchmark's core environment with no numpy. Reuses
``voice_engine.metrics.compute_audio_stats`` for level/silence stats and adds a
Goertzel-based tonality analysis.

Honesty note: acoustic *real-vs-synthetic* speech discrimination is not
reliable from the waveform, so this classifier reports **speech vs tone vs
silence vs corrupted** — provenance (was it produced by Kokoro?) is tracked
separately by the pipeline, not guessed here.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.shared_utils.audio_io import WavData, read_wav
from voice_engine.metrics.audio_stats import compute_audio_stats


class AudioClass(str, Enum):
    SPEECH = "speech"          # broadband, amplitude-modulated -> real driving audio
    TONE = "tone"              # near-pure sinusoid -> placeholder / synthetic filler
    SILENT = "silent"          # essentially no signal
    CORRUPTED = "corrupted"    # unreadable / not 16-bit PCM WAV
    MISSING = "missing"        # file absent
    EMPTY = "empty"            # zero frames


# --- classification thresholds (calibrated against real Kokoro WAVs vs a 220 Hz
#     placeholder; see tests/test_audio_validation.py for the pinned behaviour) -
_SILENCE_RMS_DBFS = -50.0        # below this overall level -> silent
_SILENCE_RATIO = 0.98            # or ~all frames below the silence floor
_TONE_TONAL_RATIO = 0.55         # >= this share of spectral energy in one bin -> tonal
_TONE_ENVELOPE_CV = 0.20         # AND envelope this flat -> steady tone (not speech)


@dataclass
class AudioValidation:
    """Full per-file audio verdict + the numbers behind it."""

    path: str
    exists: bool
    audio_class: str
    is_speech: bool
    is_placeholder: bool
    reason: str
    # waveform summary
    duration_s: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    file_size_bytes: int | None = None
    rms_dbfs: float | None = None
    peak_dbfs: float | None = None
    silence_ratio: float | None = None
    crest_factor: float | None = None
    zero_crossing_rate: float | None = None
    dominant_hz: float | None = None
    dominant_freqs: list[float] = field(default_factory=list)
    spectral_flatness: float | None = None
    tonal_energy_ratio: float | None = None
    envelope_cv: float | None = None
    # optional expectation checks
    expected_duration_s: float | None = None
    duration_ok: bool | None = None

    @property
    def valid(self) -> bool:
        return self.audio_class == AudioClass.SPEECH.value

    def to_dict(self) -> dict:
        return {**asdict(self), "valid": self.valid}


# --------------------------------------------------------------------------- spectral
def _goertzel_power(samples, sample_rate: int, freq: float) -> float:
    """Single-frequency power via the Goertzel algorithm (stdlib)."""
    coeff = 2.0 * math.cos(2.0 * math.pi * freq / sample_rate)
    s_prev = s_prev2 = 0.0
    for x in samples:
        s = x + coeff * s_prev - s_prev2
        s_prev2, s_prev = s_prev, s
    return s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2


def _loudest_window(samples, frame: int):
    """Return the ~frame-length slice with the most energy (skips leading silence)."""
    n = len(samples)
    if n <= frame:
        return samples
    best_start, best_energy = 0, -1.0
    step = max(1, frame // 2)
    for start in range(0, n - frame, step):
        window = samples[start:start + frame]
        energy = sum(s * s for s in window)
        if energy > best_energy:
            best_energy, best_start = energy, start
    return samples[best_start:best_start + frame]


def _spectrum(wav: WavData) -> tuple[float, list[float], float, float]:
    """(dominant_hz, top_freqs, spectral_flatness, tonal_energy_ratio).

    Downsamples to ~8 kHz and runs Goertzel over a coarse 0-4 kHz grid on the
    loudest window — cheap and enough to separate a pure tone from speech.
    """
    sr = wav.sample_rate or 1
    decim = max(1, sr // 8000)
    ds_rate = sr / decim
    mono = wav.samples[:: wav.channels] if wav.channels > 1 else wav.samples
    window = _loudest_window(mono, min(len(mono), int(sr * 0.35)))
    ds = window[::decim]
    if len(ds) < 32:
        return (0.0, [], 1.0, 0.0)

    nyq = ds_rate / 2.0
    hi = min(4000.0, nyq - 1)
    step = 40.0
    freqs = [f for f in _frange(60.0, hi, step)]
    powers = [max(_goertzel_power(ds, ds_rate, f), 0.0) for f in freqs]
    total = sum(powers) or 1e-12

    ranked = sorted(zip(freqs, powers), key=lambda fp: fp[1], reverse=True)
    dominant_hz = ranked[0][0] if ranked else 0.0
    top_freqs = [round(f, 1) for f, _ in ranked[:3]]
    tonal_ratio = ranked[0][1] / total if ranked else 0.0

    # spectral flatness = geometric mean / arithmetic mean (0 tonal .. 1 flat)
    eps = 1e-12
    log_mean = sum(math.log(p + eps) for p in powers) / len(powers)
    geo = math.exp(log_mean)
    arith = total / len(powers)
    flatness = min(1.0, max(0.0, geo / arith)) if arith > 0 else 1.0  # AM-GM bounds to [0,1]
    return (round(dominant_hz, 1), top_freqs, round(flatness, 5), round(tonal_ratio, 5))


def _frange(start: float, stop: float, step: float):
    x = start
    while x <= stop:
        yield x
        x += step


def _envelope_cv(wav: WavData) -> float:
    """Coefficient of variation of short-time RMS (envelope modulation).

    ~0 for a steady tone; large for speech (syllables, pauses)."""
    sr = wav.sample_rate or 1
    frame = max(1, int(sr * 0.03))
    rms_vals: list[float] = []
    s = wav.samples[:: wav.channels] if wav.channels > 1 else wav.samples
    for start in range(0, len(s), frame):
        f = s[start:start + frame]
        if not len(f):
            continue
        rms_vals.append(math.sqrt(sum(x * x for x in f) / len(f)))
    if not rms_vals:
        return 0.0
    mean = sum(rms_vals) / len(rms_vals)
    if mean <= 1e-9:
        return 0.0
    var = sum((r - mean) ** 2 for r in rms_vals) / len(rms_vals)
    return math.sqrt(var) / mean


def _zero_crossing_rate(wav: WavData) -> float:
    s = wav.samples[:: wav.channels] if wav.channels > 1 else wav.samples
    if len(s) < 2:
        return 0.0
    crossings = sum(1 for i in range(1, len(s)) if (s[i - 1] >= 0) != (s[i] >= 0))
    return crossings / (len(s) / (wav.sample_rate or 1))


# --------------------------------------------------------------------------- validate
def validate_wav(path: Path | str, expected_duration_s: float | None = None) -> AudioValidation:
    """Inspect and classify one WAV file."""
    p = Path(path)
    if not p.exists():
        return AudioValidation(str(p), False, AudioClass.MISSING.value, False, False,
                               reason="file does not exist")
    size = p.stat().st_size
    try:
        wav = read_wav(p)
    except PlatformError as exc:
        return AudioValidation(str(p), True, AudioClass.CORRUPTED.value, False, False,
                               reason=f"unreadable WAV: {exc}", file_size_bytes=size)

    if wav.n_frames == 0:
        return AudioValidation(str(p), True, AudioClass.EMPTY.value, False, False,
                               reason="WAV has zero audio frames", file_size_bytes=size,
                               sample_rate=wav.sample_rate, channels=wav.channels)

    stats = compute_audio_stats(wav)
    dominant_hz, top_freqs, flatness, tonal_ratio = _spectrum(wav)
    env_cv = round(_envelope_cv(wav), 5)
    zcr = round(_zero_crossing_rate(wav), 1)
    peak_lin = 10 ** (stats.peak_dbfs / 20)
    rms_lin = 10 ** (stats.rms_dbfs / 20)
    crest = round(peak_lin / rms_lin, 3) if rms_lin > 0 else None

    v = AudioValidation(
        path=str(p), exists=True, audio_class="", is_speech=False, is_placeholder=False,
        reason="", duration_s=round(wav.duration_s, 3), sample_rate=wav.sample_rate,
        channels=wav.channels, file_size_bytes=size, rms_dbfs=round(stats.rms_dbfs, 2),
        peak_dbfs=round(stats.peak_dbfs, 2), silence_ratio=round(stats.silence_ratio, 4),
        crest_factor=crest, zero_crossing_rate=zcr, dominant_hz=dominant_hz,
        dominant_freqs=top_freqs, spectral_flatness=flatness, tonal_energy_ratio=tonal_ratio,
        envelope_cv=env_cv, expected_duration_s=expected_duration_s,
    )

    # --- classify -------------------------------------------------------------
    if stats.rms_dbfs < _SILENCE_RMS_DBFS or stats.silence_ratio >= _SILENCE_RATIO:
        v.audio_class = AudioClass.SILENT.value
        v.reason = (f"silent: rms {stats.rms_dbfs:.1f} dBFS, "
                    f"silence {stats.silence_ratio*100:.0f}% (need real speech)")
    elif tonal_ratio >= _TONE_TONAL_RATIO and env_cv < _TONE_ENVELOPE_CV:
        v.audio_class = AudioClass.TONE.value
        v.is_placeholder = True
        v.reason = (f"placeholder tone: {tonal_ratio*100:.0f}% of energy at "
                    f"{dominant_hz:.0f} Hz with a flat envelope (cv={env_cv:.2f})")
    else:
        v.audio_class = AudioClass.SPEECH.value
        v.is_speech = True
        v.reason = (f"speech: broadband (tonal {tonal_ratio*100:.0f}%), "
                    f"modulated envelope (cv={env_cv:.2f})")

    if expected_duration_s is not None:
        v.duration_ok = abs(wav.duration_s - expected_duration_s) <= max(0.5, 0.25 * expected_duration_s)
    return v


def validate_kokoro_output(
    path: Path | str, expected_duration_s: float | None = None
) -> AudioValidation:
    """Validate a Kokoro synthesis result: real speech + (optional) duration."""
    v = validate_wav(path, expected_duration_s=expected_duration_s)
    if v.valid and v.duration_ok is False:
        v.reason += (f"; duration {v.duration_s:.1f}s off expected "
                     f"{expected_duration_s:.1f}s")
    return v


def write_audio_validation_report(
    validations, out_dir: Path, label_by_path: dict[str, str] | None = None
) -> dict[str, Path]:
    """Write ``audio_validation_report.{json,md}`` for a set of validations.

    ``label_by_path`` optionally maps a WAV path -> source script text so the
    report shows what each clip was supposed to say.
    """
    import json

    from foundation.shared_utils.timing import utc_now_iso

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = label_by_path or {}
    generated_at = utc_now_iso()
    items = list(validations)

    json_path = out_dir / "audio_validation_report.json"
    json_path.write_text(
        json.dumps(
            {"generated_at": generated_at,
             "summary": {"total": len(items),
                         "speech": sum(v.valid for v in items),
                         "placeholder": sum(v.is_placeholder for v in items),
                         "invalid": sum(not v.valid for v in items)},
             "files": [{**v.to_dict(), "source_script": labels.get(v.path, "")}
                       for v in items]},
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Audio Validation Report", "", f"Generated: {generated_at}", "",
        f"**{sum(v.valid for v in items)}/{len(items)} files are real speech** · "
        f"{sum(v.is_placeholder for v in items)} placeholder tone(s) · "
        f"{sum(v.audio_class == AudioClass.SILENT.value for v in items)} silent · "
        f"{sum(v.audio_class in (AudioClass.CORRUPTED.value, AudioClass.MISSING.value, AudioClass.EMPTY.value) for v in items)} unreadable/missing.",
        "",
        "| File | Class | Speech | Placeholder | Dur (s) | RMS dBFS | Silence % | Dom Hz | Env cv | Size (KB) |",
        "|---|---|:--:|:--:|--:|--:|--:|--:|--:|--:|",
    ]
    for v in items:
        name = Path(v.path).name
        lines.append(
            f"| {name} | {v.audio_class} | {'Yes' if v.is_speech else 'No'} | "
            f"{'YES' if v.is_placeholder else 'no'} | "
            f"{_g(v.duration_s)} | {_g(v.rms_dbfs)} | "
            f"{_pct(v.silence_ratio)} | {_g(v.dominant_hz)} | {_g(v.envelope_cv)} | "
            f"{round(v.file_size_bytes/1024,1) if v.file_size_bytes else '—'} |"
        )
    lines.append("")
    lines.append("## Detail")
    for v in items:
        lines += [
            "", f"### {Path(v.path).name} — {v.audio_class.upper()}", "",
            f"- Verdict: **{'REAL SPEECH' if v.is_speech else 'NOT USABLE'}** — {v.reason}",
        ]
        if labels.get(v.path):
            lines.append(f"- Source script: \"{labels[v.path][:120]}\"")
        lines.append(
            f"- duration={_g(v.duration_s)}s · sample_rate={v.sample_rate} · "
            f"channels={v.channels} · rms={_g(v.rms_dbfs)} dBFS · peak={_g(v.peak_dbfs)} dBFS · "
            f"silence={_pct(v.silence_ratio)} · crest={_g(v.crest_factor)}"
        )
        lines.append(
            f"- dominant={_g(v.dominant_hz)} Hz · top_freqs={v.dominant_freqs} · "
            f"tonal_ratio={_g(v.tonal_energy_ratio)} · spectral_flatness={_g(v.spectral_flatness)} · "
            f"envelope_cv={_g(v.envelope_cv)} · zcr={_g(v.zero_crossing_rate)}"
        )
    md_path = out_dir / "audio_validation_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _g(x) -> str:
    return "—" if x is None else (f"{x:g}" if isinstance(x, float) else str(x))


def _pct(x) -> str:
    return "—" if x is None else f"{x*100:.0f}%"
