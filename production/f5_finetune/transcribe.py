"""Stage 1 — transcribe accepted production segments (runs inside the f5 venv).

    <venv python> -m production.f5_finetune.transcribe [--limit N] [--model small]

Reads the production dataset READ-ONLY; writes to the workspace:
    transcripts/transcripts.csv   full per-segment record (raw + romanized text)
    transcripts/metadata.csv      F5 training manifest: `audio_file|text`
    transcripts/transcribe_report.json

Romanization: F5TTS_v1_Base ships the Emilia ZH/EN vocab — Devanagari is NOT
in it, so Hindi text must be romanized (ITRANS via indic-transliteration,
lowercased) to stay inside the pretrained charset. prepare.py hard-verifies
the result against the actual vocab before building the arrow dataset.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from production.f5_finetune.common import accepted_rows, load_config, workspace_dir  # noqa: E402

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

#: Whisper likes curly punctuation and invisible marks; the pretrained vocab
#: does not. Normalize BEFORE the charset check instead of failing on them.
_CHAR_MAP = {"“": '"', "”": '"', "‘": "'", "’": "'",
             "—": "-", "–": "-", "…": "...",
             "​": "", "‌": "", "‍": "", "﻿": "", " ": " "}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    return " ".join(text.split())


def romanize(text: str) -> str:
    """Devanagari -> lowercase Latin (ITRANS); Latin/digits/punct unchanged.

    Dandas are mapped to '.' FIRST — ITRANS would turn them into '|', which is
    the metadata.csv field delimiter (found in the T3 sample run). Candra
    vowels (ऑ/ॉ/ऍ/ॅ — English loanwords like "office" in Hindi script) are
    folded to their plain forms first: ITRANS passes them through untouched,
    which broke the T4 run (177/521 transcripts rejected by the vocab check).
    """
    text = text.replace("।", ". ").replace("॥", ". ")
    text = (text.replace("ऑ", "ओ").replace("ॉ", "ो")
                .replace("ऍ", "ए").replace("ॅ", "े"))
    if not _DEVANAGARI.search(text):
        return text
    from indic_transliteration import sanscript

    latin = sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    return latin.lower().replace("|", " ")


def _write_outputs(out_dir: Path, records: list[dict], dropped: list[dict],
                   report: dict) -> None:
    with open(out_dir / "transcripts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list((records + dropped)[0].keys()))
        w.writeheader()
        w.writerows(records + dropped)
    # F5 manifest: pipe-delimited, header required, absolute audio paths.
    with open(out_dir / "metadata.csv", "w", newline="", encoding="utf-8") as f:
        f.write("audio_file|text\n")
        for r in records:
            f.write(f"{r['audio_file']}|{r['text'].replace('|', ' ')}\n")
    (out_dir / "transcribe_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def re_romanize(cfg: dict) -> int:
    """Re-render text from stored text_raw with the CURRENT romanization rules.

    No Whisper involved — lets romanization fixes apply retroactively to an
    existing (expensive) transcription run instead of redoing it.
    """
    tcfg = cfg["transcription"]
    out_dir = workspace_dir(cfg) / "transcripts"
    tr_csv = out_dir / "transcripts.csv"
    with open(tr_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    records, dropped = [], []
    for r in rows:
        r["text"] = normalize_text(romanize(r["text_raw"]) if tcfg["romanize"] else r["text_raw"])
        bad = (len(r["text"]) < tcfg["min_chars"]
               or float(r["no_speech_prob"]) > tcfg["max_no_speech_prob"])
        (dropped if bad else records).append(r)
    old_report = {}
    rep_path = out_dir / "transcribe_report.json"
    if rep_path.exists():
        old_report = json.loads(rep_path.read_text(encoding="utf-8"))
    report = {**old_report, "kept": len(records), "dropped": len(dropped),
              "re_romanized": True}
    _write_outputs(out_dir, records, dropped, report)
    print(f"[transcribe] re-romanized {len(rows)} existing transcripts "
          f"(kept {len(records)}) -> {out_dir / 'metadata.csv'}")
    return 0 if records else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcribe accepted segments for F5 fine-tuning")
    parser.add_argument("--limit", type=int, default=0, help="Only N segments (0 = all)")
    parser.add_argument("--model", default=None, help="Override whisper model id")
    parser.add_argument("--re-romanize", action="store_true",
                        help="Recompute text from existing transcripts.csv (no Whisper)")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.re_romanize:
        return re_romanize(cfg)
    tcfg = cfg["transcription"]
    rows = accepted_rows(cfg)
    if args.limit:
        rows = rows[: args.limit]

    from faster_whisper import WhisperModel

    try:
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        device = "cpu"
    compute = tcfg["compute_type"]
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    model_id = args.model or tcfg["whisper_model"]
    print(f"[transcribe] whisper={model_id} device={device} compute={compute} "
          f"segments={len(rows)}", flush=True)
    model = WhisperModel(model_id, device=device, compute_type=compute)

    out_dir = workspace_dir(cfg) / "transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    records, dropped = [], []
    t0 = time.time()
    for i, row in enumerate(rows, 1):
        wav = row["resolved_audio"]
        # condition_on_previous_text=False curbs the repetition loops whisper
        # falls into on code-switched speech (seen in the T3 sample run).
        segments, info = model.transcribe(wav, language=tcfg["language"], vad_filter=True,
                                          beam_size=5, condition_on_previous_text=False)
        parts, no_speech = [], []
        for seg in segments:
            parts.append(seg.text.strip())
            no_speech.append(seg.no_speech_prob)
        raw = " ".join(p for p in parts if p).strip()
        text = normalize_text(romanize(raw) if tcfg["romanize"] else raw)
        worst_no_speech = max(no_speech) if no_speech else 1.0
        rec = {
            "segment_file": row["segment_file"],
            "audio_file": wav,
            "duration": row["duration"],
            "snr_db": row["snr_db"],
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "no_speech_prob": round(worst_no_speech, 3),
            "text_raw": raw,
            "text": text,
        }
        if len(text) < tcfg["min_chars"] or worst_no_speech > tcfg["max_no_speech_prob"]:
            dropped.append(rec)
        else:
            records.append(rec)
        if i % 25 == 0 or i == len(rows):
            print(f"[transcribe] {i}/{len(rows)} ({time.time() - t0:.0f}s)", flush=True)

    langs: dict[str, int] = {}
    for r in records:
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    report = {
        "whisper_model": model_id, "device": device, "compute_type": compute,
        "segments_in": len(rows), "kept": len(records), "dropped": len(dropped),
        "languages": langs, "romanized": tcfg["romanize"],
        "elapsed_s": round(time.time() - t0, 1),
    }
    _write_outputs(out_dir, records, dropped, report)
    print(f"[transcribe] kept {len(records)}/{len(rows)} -> {out_dir / 'metadata.csv'}")
    return 0 if records else 1


if __name__ == "__main__":
    raise SystemExit(main())
