"""Run the voice model benchmark.

Examples:
    python -m voice_engine.scripts.run_benchmark --adapters mock --languages en
    python -m voice_engine.scripts.run_benchmark --adapters f5-tts xtts-v2 \
        --languages en hi hi-en --reference-audio voice_engine/datasets/reference_audio/male_hi_20s.wav \
        --reference-text "<transcript of the clip>"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import LogFormat, configure_logging  # noqa: E402
from voice_engine.adapters import ADAPTER_CLASSES, register_all_specs  # noqa: E402
from voice_engine.benchmark import VoiceBenchmark, VoiceBenchmarkConfig  # noqa: E402
from voice_engine.reporting import summarize_run  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Voice cloning model benchmark")
    parser.add_argument("--adapters", nargs="+", default=["mock"],
                        choices=sorted(ADAPTER_CLASSES), help="Adapter ids to benchmark")
    parser.add_argument("--languages", nargs="+", default=["en", "hi", "hi-en", "bn"],
                        choices=["en", "hi", "hi-en", "bn"])
    parser.add_argument("--categories", nargs="*", default=[],
                        help="Prompt categories to include (default: all)")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-items", type=int, default=0,
                        help="Cap prompts per language (0 = all); for slow CPU-only runs")
    parser.add_argument("--reference-audio", default=None, help="Reference WAV for cloning")
    parser.add_argument("--reference-text", default="", help="Transcript of the reference WAV")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--no-streaming", action="store_true", help="Skip streaming scenario")
    parser.add_argument("--json-logs", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(log_format=LogFormat.JSON if args.json_logs else LogFormat.TEXT)
    register_all_specs()

    config = VoiceBenchmarkConfig(
        adapters=args.adapters,
        languages=args.languages,
        categories=args.categories,
        max_items_per_language=args.max_items,
        repetitions=args.repetitions,
        include_streaming_scenario=not args.no_streaming,
        reference_audio=args.reference_audio,
        reference_text=args.reference_text,
        device=args.device,
    )
    if args.output_dir:
        config.output_dir = args.output_dir

    run, reports = VoiceBenchmark(config).run()

    summary = summarize_run(run)
    print(f"\nRun {run.run_id} complete.")
    for subject in summary.subjects:
        rtf = subject.metric_means.get("real_time_factor")
        print(
            f"  {subject.subject_id}: {subject.passed} passed, {subject.failed} failed, "
            f"{subject.skipped} skipped" + (f", mean RTF {rtf}" if rtf is not None else "")
        )
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(s.failed for s in summary.subjects)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
