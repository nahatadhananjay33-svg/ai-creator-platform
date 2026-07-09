"""Dependency-free audio mixing primitives (Phase C8).

Pure, deterministic DSP on plain ``list[float]`` sample buffers in the normalized
``[-1.0, 1.0]`` domain — no numpy, no scipy, no external deps, so the Music
Engine and both renderers mix audio identically on any machine. Every function
is a pure transform (no I/O, no globals, no randomness): the same inputs always
produce byte-identical output, which is what makes the mixed reel reproducible.

The building blocks: int16 <-> float conversion, nearest-neighbour resampling,
looping/tiling (with an optional crossfade seam), linear fades, a piecewise-
linear volume envelope, slew-limited speech ducking, summation, and a soft
limiter that guarantees the result can never clip. Heavier analysis (spectral
metrics, high-quality resampling) is intentionally out of scope here.
"""
from __future__ import annotations

import array
import math

#: Full-scale for signed 16-bit PCM. int16 spans [-32768, 32767]; we scale by
#: 32767 so +1.0 maps to the max positive sample and -1.0 to -32767 (symmetric).
_INT16_PEAK = 32767


def to_float(samples) -> list[float]:
    """Convert 16-bit PCM samples (an ``array('h')`` / iterable) to floats in
    ``[-1, 1]``."""
    inv = 1.0 / 32768.0
    return [s * inv for s in samples]


def to_int16(samples: list[float]) -> "array.array":
    """Convert normalized floats to a 16-bit PCM ``array('h')``.

    Values are hard-clamped to ``[-1, 1]`` first so the cast can never wrap; pair
    with :func:`soft_limit` upstream to avoid audible clipping (this clamp is only
    the last-resort guarantee that the integer conversion is in range)."""
    out = array.array("h")
    for s in samples:
        if s >= 1.0:
            out.append(_INT16_PEAK)
        elif s <= -1.0:
            out.append(-_INT16_PEAK)
        else:
            out.append(int(s * _INT16_PEAK))
    return out


def resample_nearest(samples: list[float], src_sr: int, dst_sr: int) -> list[float]:
    """Nearest-neighbour resample from ``src_sr`` to ``dst_sr`` (deterministic).

    Deliberately simple (no filtering): music beds are usually already at the
    render rate, and nearest-neighbour keeps the transform exact and reproducible
    when they are not. Returns the input unchanged when the rates match."""
    if src_sr == dst_sr or not samples:
        return list(samples)
    n_out = max(1, int(round(len(samples) * dst_sr / src_sr)))
    ratio = src_sr / dst_sr
    n_in = len(samples)
    return [samples[min(n_in - 1, int(i * ratio))] for i in range(n_out)]


def tile_to_length(samples: list[float], n: int, crossfade_n: int = 0) -> list[float]:
    """Loop ``samples`` to exactly ``n`` samples.

    With ``crossfade_n > 0`` each new iteration is linearly cross-faded over the
    previous one's tail so the loop seam is inaudible (a short equal-ish blend);
    with ``crossfade_n == 0`` iterations are butted end to end. Returns ``n``
    samples (zero-padded if the source is empty)."""
    if n <= 0:
        return []
    src = list(samples)
    if not src:
        return [0.0] * n
    period = len(src)
    xf = max(0, min(crossfade_n, period // 2))
    if xf == 0:                                 # simple butt-join tiling
        return [src[i % period] for i in range(n)]

    out: list[float] = []
    while len(out) < n:
        if not out:
            out.extend(src)
            continue
        # cross-fade the first xf samples of this iteration over the last xf of out
        for k in range(xf):
            w = (k + 1) / (xf + 1)              # 0<w<1: ramp new in, old out
            j = len(out) - xf + k
            out[j] = out[j] * (1.0 - w) + src[k] * w
        out.extend(src[xf:])
    return out[:n]


def apply_fades(samples: list[float], sr: int, fade_in_s: float,
                fade_out_s: float) -> list[float]:
    """Return ``samples`` with a linear fade-in and fade-out applied in place-style.

    Fades are clamped so they never overlap (each capped at half the buffer). A
    zero-length fade is a no-op. Mutates and returns the same list for speed."""
    n = len(samples)
    if n == 0:
        return samples
    fi = min(int(round(max(0.0, fade_in_s) * sr)), n // 2)
    fo = min(int(round(max(0.0, fade_out_s) * sr)), n // 2)
    for i in range(fi):
        samples[i] *= (i + 1) / (fi + 1)
    for i in range(fo):
        samples[n - 1 - i] *= (i + 1) / (fo + 1)
    return samples


def envelope_gains(points, sr: int, n: int, offset_s: float = 0.0) -> list[float]:
    """Piecewise-linear gain curve sampled at ``sr`` for ``n`` samples.

    ``points`` is ``[(time_s, gain), ...]`` in ABSOLUTE reel time; ``offset_s`` is
    the buffer's start in that timeline (so a clip placed at ``start_s`` passes
    ``offset_s=start_s``). Gain is linearly interpolated between points and held
    flat before the first / after the last. An empty ``points`` yields a constant
    ``1.0`` (no automation)."""
    pts = sorted(points, key=lambda p: p[0])
    if not pts:
        return [1.0] * n
    gains = [1.0] * n
    for i in range(n):
        t = offset_s + i / sr
        if t <= pts[0][0]:
            gains[i] = pts[0][1]
        elif t >= pts[-1][0]:
            gains[i] = pts[-1][1]
        else:
            # find the segment [a, b] containing t (linear scan; points are few)
            for k in range(1, len(pts)):
                if t <= pts[k][0]:
                    (ta, ga), (tb, gb) = pts[k - 1], pts[k]
                    frac = 0.0 if tb == ta else (t - ta) / (tb - ta)
                    gains[i] = ga + (gb - ga) * frac
                    break
    return gains


def ducking_gains(n: int, sr: int, speech_windows, *, duck_level: float,
                  attack_s: float, release_s: float, pad_s: float = 0.0,
                  offset_s: float = 0.0) -> list[float]:
    """Slew-limited ducking gain: ``1.0`` in the clear, ``duck_level`` under speech.

    ``speech_windows`` is ``[(start_s, end_s), ...]`` in ABSOLUTE reel time
    (optionally widened by ``pad_s`` each side); ``offset_s`` maps sample 0 to its
    absolute time. The target is ``duck_level`` while speech is present and ``1.0``
    otherwise; the returned envelope ramps toward the target no faster than
    ``attack_s`` (going down) / ``release_s`` (coming back up), so there are no
    clicks. Fully deterministic — it reads the *plan*, never the waveform."""
    if not speech_windows:
        return [1.0] * n
    wins = sorted((s - pad_s, e + pad_s) for s, e in speech_windows)

    def _in_speech(t: float) -> bool:
        for s, e in wins:
            if s <= t <= e:
                return True
            if s > t:
                break
        return False

    down = (1.0 - duck_level) / max(1e-9, attack_s * sr)   # per-sample slew rates
    up = (1.0 - duck_level) / max(1e-9, release_s * sr)
    gains = [1.0] * n
    # seed at the target for sample 0 so a clip that opens under speech is ducked.
    g = duck_level if _in_speech(offset_s) else 1.0
    for i in range(n):
        target = duck_level if _in_speech(offset_s + i / sr) else 1.0
        if target < g:
            g = max(target, g - down)
        elif target > g:
            g = min(target, g + up)
        gains[i] = g
    return gains


def apply_gains(samples: list[float], gains: list[float]) -> list[float]:
    """Multiply ``samples`` by a per-sample ``gains`` curve (in place)."""
    for i in range(min(len(samples), len(gains))):
        samples[i] *= gains[i]
    return samples


def apply_mute_sections(samples: list[float], sr: int, sections,
                        offset_s: float = 0.0) -> list[float]:
    """Zero out ``samples`` inside each absolute ``(start_s, end_s)`` section."""
    n = len(samples)
    for s, e in sections:
        i0 = max(0, int(round((s - offset_s) * sr)))
        i1 = min(n, int(round((e - offset_s) * sr)))
        for i in range(i0, i1):
            samples[i] = 0.0
    return samples


def mix_into(dst: list[float], src: list[float], offset_n: int = 0) -> list[float]:
    """Add ``src`` into ``dst`` starting at sample ``offset_n`` (in place).

    ``dst`` is assumed long enough; samples past its end are dropped. This is the
    summation step — voice + one or more music beds — before limiting."""
    m = len(dst)
    for i, v in enumerate(src):
        j = offset_n + i
        if 0 <= j < m:
            dst[j] += v
        elif j >= m:
            break
    return dst


def peak(samples) -> float:
    """The maximum absolute sample value (0.0 for an empty buffer)."""
    return max((abs(s) for s in samples), default=0.0)


def soft_limit(samples: list[float], threshold: float = 0.8) -> list[float]:
    """Soft-knee limiter guaranteeing ``|out| < 1`` (so the mix never clips).

    Below ``threshold`` samples pass through untouched; above it the excess is
    compressed through a ``tanh`` knee that asymptotes to 1.0. This is smooth and
    deterministic, so a hot mix is tamed without the harsh flat-topping of hard
    clipping. Mutates and returns the same list."""
    t = max(0.0, min(0.999, threshold))
    span = 1.0 - t
    for i, s in enumerate(samples):
        a = abs(s)
        if a <= t:
            continue
        limited = t + span * math.tanh((a - t) / span)
        samples[i] = math.copysign(limited, s)
    return samples
