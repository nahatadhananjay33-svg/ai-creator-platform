"""Consistency Engine (Phase C13) — project-wide visual coherence, deterministically.

Given the assets assigned across a project's scenes, it detects repeated people,
colours, logos/brands, and styles and flags inconsistencies — the sort of thing
that makes a reel feel disjointed (three different colour palettes, a person shown
in clashing styles, a stray third-party logo). It is **metadata-only and
deterministic**: it reads descriptive fields the registry already carries
(``dominant_color``, ``style``, ``subject``, ``brand``) and applies fixed rules —
NO pixels are decoded, NO model runs, and the same assignment always yields the
same report. It never mutates anything.
"""
from __future__ import annotations

from dataclasses import dataclass

from editing_engine.project import ReelProject

from media_intelligence.recommend import ProjectRecommendations
from media_intelligence.registry import RegisteredAsset

#: Default tolerance: how many distinct palettes / styles read as still-coherent.
_MAX_PALETTE = 3
_MAX_STYLES = 2
#: Per-dimension penalty applied to the consistency score for each warning.
_PENALTY = {"color": 0.2, "style": 0.2, "subject": 0.25, "brand": 0.3, "family": 0.1}


@dataclass(frozen=True)
class ConsistencyFinding:
    """One coherence note: a dimension, a severity, a message, and the scenes."""

    dimension: str                       # color | style | subject | brand | family
    severity: str                        # "info" | "warning"
    message: str
    scene_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class ConsistencyReport:
    """The result of a consistency pass: findings + a score + dimension summaries.

    ``consistency_score`` is 1.0 for a fully coherent set, reduced by a fixed
    penalty per warning (floored at 0). The ``*_by_scene`` summaries expose what
    was observed on each dimension so a UI can render the palette/style/subject
    make-up directly."""

    n_assets: int
    consistency_score: float
    findings: tuple[ConsistencyFinding, ...]
    colors_by_scene: tuple[tuple[int, str], ...]
    styles_by_scene: tuple[tuple[int, str], ...]
    subjects_by_scene: tuple[tuple[int, str], ...]
    brands_by_scene: tuple[tuple[int, str], ...]

    @property
    def warnings(self) -> tuple[ConsistencyFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "warning")

    @property
    def infos(self) -> tuple[ConsistencyFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "info")

    @property
    def consistent(self) -> bool:
        """True when nothing warned (infos are advisory)."""
        return not self.warnings

    @property
    def distinct_colors(self) -> tuple[str, ...]:
        return tuple(sorted({c for _, c in self.colors_by_scene}))

    @property
    def distinct_styles(self) -> tuple[str, ...]:
        return tuple(sorted({s for _, s in self.styles_by_scene}))

    @property
    def recurring_subjects(self) -> tuple[str, ...]:
        counts: dict[str, int] = {}
        for _, s in self.subjects_by_scene:
            counts[s] = counts.get(s, 0) + 1
        return tuple(sorted(s for s, n in counts.items() if n >= 2))


def _collect(assignments, field: str) -> tuple[tuple[int, str], ...]:
    """Scene→value pairs for a metadata ``field`` (only assets that carry it)."""
    out = []
    for idx in sorted(assignments):
        value = assignments[idx].meta.get(field)
        if value:
            out.append((idx, str(value)))
    return tuple(out)


def _distinct(pairs) -> dict[str, list[int]]:
    """Map each distinct value to the sorted scene indices that carry it."""
    groups: dict[str, list[int]] = {}
    for idx, value in pairs:
        groups.setdefault(value, []).append(idx)
    return {k: sorted(v) for k, v in sorted(groups.items())}


class ConsistencyEngine:
    """Detects repeated people/colours/logos/styles and flags inconsistencies."""

    def __init__(self, *, max_palette: int = _MAX_PALETTE, max_styles: int = _MAX_STYLES) -> None:
        self.max_palette = max_palette
        self.max_styles = max_styles

    def analyze(self, assignments: dict[int, RegisteredAsset], *,
                project: ReelProject | None = None) -> ConsistencyReport:
        """Analyze a scene→asset assignment for project-wide visual consistency."""
        colors = _collect(assignments, "dominant_color")
        styles = _collect(assignments, "style")
        subjects = _collect(assignments, "subject")
        brands = _collect(assignments, "brand")
        families = tuple((idx, assignments[idx].family) for idx in sorted(assignments))

        findings: list[ConsistencyFinding] = []

        # colour palette coherence
        color_groups = _distinct(colors)
        if len(color_groups) > self.max_palette:
            findings.append(ConsistencyFinding(
                "color", "warning",
                f"palette is fragmented: {len(color_groups)} distinct dominant colours "
                f"({', '.join(color_groups)})",
                tuple(sorted(i for _, i in [(0, idx) for idx, _ in colors]))))

        # style coherence
        style_groups = _distinct(styles)
        if len(style_groups) > self.max_styles:
            findings.append(ConsistencyFinding(
                "style", "warning",
                f"styles are mixed: {len(style_groups)} distinct styles "
                f"({', '.join(style_groups)})",
                tuple(idx for idx, _ in styles)))

        # repeated people + per-person style coherence
        subject_groups = _distinct(subjects)
        for subject, idxs in subject_groups.items():
            if len(idxs) >= 2:
                findings.append(ConsistencyFinding(
                    "subject", "info",
                    f"'{subject}' recurs across {len(idxs)} scenes", tuple(idxs)))
                seen_styles = {assignments[i].meta.get("style") for i in idxs
                               if assignments[i].meta.get("style")}
                if len(seen_styles) > 1:
                    findings.append(ConsistencyFinding(
                        "subject", "warning",
                        f"'{subject}' appears in inconsistent styles "
                        f"({', '.join(sorted(str(s) for s in seen_styles))})", tuple(idxs)))

        # brand / logo coherence
        brand_groups = _distinct(brands)
        theme = project.theme if project else None
        if len(brand_groups) > 1:
            findings.append(ConsistencyFinding(
                "brand", "warning",
                f"multiple brands/logos present ({', '.join(brand_groups)})",
                tuple(idx for idx, _ in brands)))
        if theme:
            foreign = {b: idxs for b, idxs in brand_groups.items() if b != theme}
            if foreign and len(brand_groups) <= 1:
                b, idxs = next(iter(foreign.items()))
                findings.append(ConsistencyFinding(
                    "brand", "warning",
                    f"brand '{b}' does not match the project theme '{theme}'", tuple(idxs)))

        # family mixing (video vs image B-roll) — advisory only
        fam_values = {f for _, f in families}
        if len(fam_values) > 1:
            findings.append(ConsistencyFinding(
                "family", "info",
                f"B-roll mixes {', '.join(sorted(fam_values))} assets",
                tuple(idx for idx, _ in families)))

        score = 1.0
        for f in findings:
            if f.severity == "warning":
                score -= _PENALTY.get(f.dimension, 0.1)
        return ConsistencyReport(
            n_assets=len(assignments), consistency_score=round(max(0.0, score), 6),
            findings=tuple(findings), colors_by_scene=colors, styles_by_scene=styles,
            subjects_by_scene=subjects, brands_by_scene=brands)

    def analyze_recommendations(self, recommendations: ProjectRecommendations, *,
                                project: ReelProject | None = None) -> ConsistencyReport:
        """Analyze the primary picks of a set of recommendations."""
        assignments = {s.scene_index: s.primary.asset
                       for s in recommendations.scenes if s.primary}
        return self.analyze(assignments, project=project)
