"""Avatar reporting: benchmark-run reports and static research comparisons.

Generic CSV/JSON reporters come from :mod:`foundation.reporting`; this
package adds the avatar-specific Markdown run report and the research
comparison report (CSV/JSON/Markdown from the catalog, with best-in-class
awards and the production recommendation).
"""

from foundation.reporting import CsvReporter, JsonReporter, Reporter, RunSummary, summarize_run

from avatar_engine.reporting.markdown_reporter import AvatarMarkdownReporter
from avatar_engine.reporting.research_report import (
    ModelAward,
    ResearchReportGenerator,
    production_readiness_score,
)

__all__ = [
    "AvatarMarkdownReporter",
    "CsvReporter",
    "JsonReporter",
    "ModelAward",
    "Reporter",
    "ResearchReportGenerator",
    "RunSummary",
    "production_readiness_score",
    "summarize_run",
]
