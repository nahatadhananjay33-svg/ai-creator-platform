"""Avatar model research: profiles, catalog, and comparison views.

The catalog is the single source of truth about candidate avatar models
(license, hardware, activity, strengths/weaknesses). The benchmark,
reporting, and installation layers all read from here — research facts are
never duplicated elsewhere.
"""

from avatar_engine.research.catalog import (
    all_profiles,
    commercial_ready_profiles,
    get_profile,
    production_candidates,
    profiles_by_task,
)
from avatar_engine.research.schema import (
    AvatarModelProfile,
    AvatarTask,
    InstallComplexity,
    MaintenanceStatus,
    RepositoryActivity,
    ResearchRatings,
)

__all__ = [
    "AvatarModelProfile",
    "AvatarTask",
    "InstallComplexity",
    "MaintenanceStatus",
    "RepositoryActivity",
    "ResearchRatings",
    "all_profiles",
    "commercial_ready_profiles",
    "get_profile",
    "production_candidates",
    "profiles_by_task",
]
