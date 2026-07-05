"""Static research comparison report (CSV + JSON + Markdown).

Generated from the research catalog alone — no benchmark run required —
so the model comparison exists the moment research facts are updated.
All ratings in these reports are ``static`` research priors; measured
values arrive with GPU benchmark runs and live in run reports instead.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from foundation.logging import get_logger
from foundation.shared_utils.timing import utc_now_iso

from avatar_engine.research.catalog import all_profiles, production_candidates
from avatar_engine.research.schema import AvatarModelProfile, MaintenanceStatus

logger = get_logger("avatar_engine.reporting.research")

_MAINTENANCE_SCORE = {
    MaintenanceStatus.ACTIVE: 1.0,
    MaintenanceStatus.SLOWING: 0.6,
    MaintenanceStatus.STALE: 0.2,
    MaintenanceStatus.ABANDONED: 0.0,
}
_INSTALL_SCORE = {"low": 1.0, "moderate": 0.7, "high": 0.4, "severe": 0.1}
#: VRAM above this contributes zero to the hardware term.
_VRAM_CEILING_GB = 24.0


def production_readiness_score(profile: AvatarModelProfile) -> float:
    """Composite 0-1 production-readiness score (documented in RECOMMENDATIONS.md).

    Weights: 35% research quality, 20% commercial license, 15% maintenance,
    15% hardware envelope (recommended VRAM vs 24 GB ceiling), 15% install
    complexity. Static by construction — measured benchmark results refine
    the quality term in Phase A4.
    """
    quality = profile.ratings.overall() / 5.0
    license_ok = 1.0 if profile.spec.license.commercial_use else 0.0
    maintenance = _MAINTENANCE_SCORE[profile.activity.maintenance]
    vram = profile.spec.hardware.recommended_vram_gb or profile.spec.hardware.min_vram_gb
    hardware = 1.0 if vram is None else max(0.0, 1.0 - min(vram, _VRAM_CEILING_GB) / _VRAM_CEILING_GB)
    install = _INSTALL_SCORE[profile.install_complexity.value]
    return round(
        0.35 * quality + 0.20 * license_ok + 0.15 * maintenance
        + 0.15 * hardware + 0.15 * install,
        4,
    )


@dataclass(frozen=True)
class ModelAward:
    """One best-in-class pick with the reasoning attached."""

    award: str
    model_id: str
    display_name: str
    rationale: str


def _pick(profiles: list[AvatarModelProfile], key, award: str, rationale_fmt: str) -> ModelAward:  # noqa: ANN001
    best = sorted(profiles, key=lambda p: (-key(p), -p.ratings.overall(), p.model_id))[0]
    return ModelAward(award, best.model_id, best.display_name, rationale_fmt.format(p=best))


def compute_awards() -> list[ModelAward]:
    """Best-in-class picks over production candidates (static ratings)."""
    candidates = production_candidates()
    awards = [
        _pick(candidates, lambda p: p.ratings.lip_sync, "best_lip_sync",
              "Highest research lip-sync rating ({p.ratings.lip_sync}/5) among production candidates"),
        _pick(candidates, lambda p: p.ratings.realism, "best_realism",
              "Highest research realism rating ({p.ratings.realism}/5) among production candidates"),
        _pick(candidates, lambda p: p.ratings.identity_consistency, "best_identity_consistency",
              "Highest identity-consistency rating ({p.ratings.identity_consistency}/5)"),
        _pick(
            candidates,
            lambda p: -(p.spec.hardware.min_vram_gb or 0.0),
            "best_lightweight",
            "Lowest VRAM floor ({p.spec.hardware.min_vram_gb:g} GB) among production candidates",
        ),
    ]
    commercial = [p for p in candidates if p.spec.license.commercial_use]
    awards.append(
        _pick(commercial, production_readiness_score, "best_production_model",
              "Highest production-readiness score among commercially usable candidates"),
    )
    return awards


class ResearchReportGenerator:
    """Writes the model comparison in CSV, JSON, and Markdown."""

    def write_all(self, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "csv": self._write_csv(output_dir),
            "json": self._write_json(output_dir),
            "markdown": self._write_markdown(output_dir),
        }
        logger.info(
            "Research comparison reports written",
            extra={"context": {k: str(v) for k, v in paths.items()}},
        )
        return paths

    # ------------------------------------------------------------------ CSV
    def _write_csv(self, output_dir: Path) -> Path:
        path = output_dir / "model_comparison.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["model_id", "display_name", "task", "code_license", "weights_license",
                 "commercial_use", "stars", "last_push", "maintenance", "min_vram_gb",
                 "recommended_vram_gb", "disk_gb", "cpu_capable", "install_complexity",
                 "os_support", "lip_sync", "realism", "identity", "expressiveness",
                 "motion", "overall_rating", "production_candidate", "readiness_score",
                 "excluded_reason"]
            )
            for p in all_profiles():
                hw = p.spec.hardware
                writer.writerow(
                    [p.model_id, p.display_name, p.task.value,
                     p.spec.license.code_license, p.spec.license.weights_license,
                     p.spec.license.commercial_use, p.activity.stars, p.activity.last_push,
                     p.activity.maintenance.value, hw.min_vram_gb, hw.recommended_vram_gb,
                     hw.disk_size_gb, hw.cpu_realtime_capable, p.install_complexity.value,
                     "|".join(p.os_support), p.ratings.lip_sync, p.ratings.realism,
                     p.ratings.identity_consistency, p.ratings.expressiveness,
                     p.ratings.motion_naturalness, p.ratings.overall(),
                     p.production_candidate, production_readiness_score(p),
                     p.excluded_reason]
                )
        return path

    # ------------------------------------------------------------------ JSON
    def _write_json(self, output_dir: Path) -> Path:
        path = output_dir / "model_comparison.json"
        payload = {
            "generated_at": utc_now_iso(),
            "rating_source": "static (research priors; see avatar_engine/research/)",
            "models": [
                {**p.to_dict(), "readiness_score": production_readiness_score(p)}
                for p in all_profiles()
            ],
            "awards": [a.__dict__ for a in compute_awards()],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ------------------------------------------------------------------ Markdown
    def _write_markdown(self, output_dir: Path) -> Path:
        profiles = all_profiles()
        candidates = production_candidates()
        ranked = sorted(candidates, key=production_readiness_score, reverse=True)
        awards = compute_awards()
        lines: list[str] = []

        lines.append("# Avatar Model Comparison (Phase A3 research)")
        lines.append("")
        lines.append(f"Generated: {utc_now_iso()}  ")
        lines.append(
            "Ratings below are **static research priors** (papers, demos, community "
            "evidence) — not our measurements. The benchmark replaces them with "
            "measured values on GPU hardware in Phase A4."
        )
        lines.append("")

        lines.append("## Comparison matrix")
        lines.append("")
        lines.append("| Model | Task | Weights license | Commercial | VRAM (min/rec GB) | "
                     "Install | Maintenance | Rating | Production? |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for p in profiles:
            hw = p.spec.hardware
            vram = (
                f"{hw.min_vram_gb:g} / {hw.recommended_vram_gb:g}"
                if hw.min_vram_gb and hw.recommended_vram_gb
                else ("CPU-capable" if hw.min_vram_gb is None else f"{hw.min_vram_gb:g} / ?")
            )
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {}/5 | {} |".format(
                    p.display_name, p.task.value, p.spec.license.weights_license,
                    "yes" if p.spec.license.commercial_use else "**NO**", vram,
                    p.install_complexity.value, p.activity.maintenance.value,
                    p.ratings.overall(),
                    "yes" if p.production_candidate else f"no — {p.excluded_reason}",
                )
            )
        lines.append("")

        lines.append("## Production readiness ranking")
        lines.append("")
        lines.append("Composite of research quality (35%), commercial license (20%), "
                     "maintenance (15%), hardware envelope (15%), install complexity (15%).")
        lines.append("")
        lines.append("| Rank | Model | Score | Key strength | Key risk |")
        lines.append("|---|---|---|---|---|")
        for i, p in enumerate(ranked, start=1):
            lines.append(
                f"| {i} | {p.display_name} | {production_readiness_score(p):.2f} "
                f"| {p.strengths[0]} | {p.weaknesses[0]} |"
            )
        lines.append("")

        lines.append("## Best in class")
        lines.append("")
        for a in awards:
            lines.append(f"- **{a.award.replace('_', ' ').title()}**: {a.display_name} — {a.rationale}")
        lp = next((p for p in candidates if p.model_id == "liveportrait"), None)
        if lp is not None and not lp.spec.license.commercial_use:
            lines.append("")
            lines.append(
                "> LivePortrait awards carry a license caveat: commercial deployment "
                "requires replacing its InsightFace detection models first."
            )
        lines.append("")

        lines.append("## Strengths and weaknesses")
        lines.append("")
        for p in profiles:
            lines.append(f"### {p.display_name} (`{p.model_id}`)")
            lines.append("")
            if p.excluded_reason:
                lines.append(f"*Excluded from production: {p.excluded_reason}*")
                lines.append("")
            lines.append("**Strengths**")
            lines.extend(f"- {s}" for s in p.strengths)
            lines.append("")
            lines.append("**Weaknesses**")
            lines.extend(f"- {w}" for w in p.weaknesses)
            lines.append("")

        lines.append("## Overall recommendation")
        lines.append("")
        top = ranked[0]
        lip = next(a for a in awards if a.award == "best_lip_sync")
        lines.append(
            f"1. **Primary avatar generation:** {top.display_name} — highest "
            f"production-readiness score ({production_readiness_score(top):.2f}); "
            f"Apache-2.0, active, and the best quality-per-GB envelope."
        )
        lines.append(
            f"2. **Lip-sync / dubbing track:** {lip.display_name} for re-syncing "
            "existing footage; MuseTalk where real-time matters."
        )
        lines.append(
            "3. **Realism ceiling (batch content):** InfiniteTalk on rented GPU "
            "capacity for hero content where minutes-per-clip latency is acceptable."
        )
        lines.append(
            "4. **Do not build on:** Sonic, FLOAT, Wav2Lip (licenses); Hallo3 "
            "(hardware economics); OmniHuman (closed)."
        )
        lines.append("")
        lines.append(
            "Validate this ordering with measured GPU benchmark runs before any "
            "Phase A4 integration commitment — see `avatar_engine/docs/BENCHMARKING.md`."
        )
        lines.append("")

        path = output_dir / "model_comparison.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
