"""Patch base + shared validation vocabularies (Phase C11).

Every edit is an immutable ``@dataclass(frozen=True)`` :class:`Patch`. A patch is a
pure value: it validates itself against a :class:`ReelProject` (returning a list
of problems, empty == valid) and, when applied, returns a NEW project — it never
mutates the input. The valid value sets (themes, soundtracks, caption kinds/styles,
asset kinds/layouts, scene types) are pulled from the engines that own them, so a
patch can never set a value a downstream engine would reject.
"""
from __future__ import annotations

from branding_engine import theme_names
from caption_engine import CAPTION_KINDS, style_names
from music_engine import soundtrack_names
from reel_engine.interfaces.types import ASSET_KINDS, ASSET_LAYOUTS
from script_engine.storyboard.types import SUPPORTED_SCENE_TYPES

from editing_engine.project import ReelProject


class Patch:
    """Base class for immutable edit operations. Concrete patches are frozen
    dataclasses that set :attr:`op` and implement :meth:`validate` + :meth:`apply`."""

    op: str = "patch"

    def validate(self, project: ReelProject) -> list[str]:
        """Return a list of problems (empty == the patch is applicable)."""
        return []

    def apply(self, project: ReelProject) -> ReelProject:  # pragma: no cover - abstract
        raise NotImplementedError

    def describe(self) -> str:
        """A short human-readable summary (for the history log)."""
        return self.op


# ---- shared value-set accessors (cached at call time; small + deterministic) --
def valid_themes() -> tuple[str, ...]:
    return tuple(theme_names())


def valid_soundtracks() -> tuple[str, ...]:
    return tuple(soundtrack_names())


def valid_caption_kinds() -> tuple[str, ...]:
    return tuple(CAPTION_KINDS)


def valid_caption_styles() -> tuple[str, ...]:
    return tuple(style_names())


VALID_ASSET_KINDS: tuple[str, ...] = tuple(ASSET_KINDS)
VALID_ASSET_LAYOUTS: tuple[str, ...] = tuple(ASSET_LAYOUTS)
VALID_SCENE_TYPES: tuple[str, ...] = tuple(SUPPORTED_SCENE_TYPES)


def _index_in_range(index: int, n: int, *, inclusive: bool = False) -> bool:
    """True if ``index`` is a valid scene position (``inclusive`` allows == n)."""
    return 0 <= index <= n if inclusive else 0 <= index < n
