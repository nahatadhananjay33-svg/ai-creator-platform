"""Load a batch of reels from CSV, JSON, or YAML (Phase C20).

One function — :func:`load_entries` — reads a batch file and returns a validated
list of :class:`~batch_runner.entry.BatchEntry`. All three formats normalize to
the same shape.

Per entry:

- ``prompt``   (required) — the idea for the reel.
- ``template`` (optional) — the content vertical.
- ``output``   (optional) — the output folder / run name (defaults to a slug of
  the prompt); must be unique across the batch.
- flat extras  (optional) — ``renderer``, ``profiles``, ``language``,
  ``creator``, ``channel``, ``quality_gate`` map onto the config sections. In
  JSON/YAML an explicit nested ``overrides`` mapping is passed through as-is.

CSV: one header row; the columns are the fields above. JSON/YAML: a list of
objects, or a mapping with a ``reels`` / ``entries`` / ``batch`` list.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from foundation.config.loader import deep_merge

from batch_runner.entry import BatchEntry
from batch_runner.errors import BatchError

#: Top-level keys that are entry fields, not overrides.
_ENTRY_KEYS = {"prompt", "template", "output", "folder", "name", "overrides"}

#: Flat extra fields and the config section they nest under.
_FLAT_FIELDS = {
    "renderer": ("generation", "renderer"),
    "profiles": ("generation", "profiles"),
    "language": ("generation", "language"),
    "creator": ("branding", "creator"),
    "channel": ("branding", "channel"),
    "quality_gate": ("quality", "gate"),
    "gate": ("quality", "gate"),
}

_LIST_KEYS = {"reels", "entries", "batch", "items"}


def load_entries(path: str | Path) -> list[BatchEntry]:
    """Read and validate a batch file into :class:`BatchEntry` objects."""
    path = Path(path)
    if not path.exists():
        raise BatchError(f"Batch file not found: {path}",
                         hint="Check the path to your CSV / JSON / YAML batch file.")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = _read_csv(path)
    elif suffix == ".json":
        raw = _read_structured(path, json.loads)
    elif suffix in (".yaml", ".yml"):
        raw = _read_structured(path, yaml.safe_load)
    else:
        raise BatchError(f"Unsupported batch format: {suffix or path.name!r}",
                         hint="Use a .csv, .json, or .yaml file.")

    entries = [_normalize(row, i) for i, row in enumerate(raw, start=1)]
    if not entries:
        raise BatchError("The batch file has no reels.",
                         hint="Add at least one entry with a 'prompt'.")
    _reject_duplicates(entries)
    return entries


# --------------------------------------------------------------------------- #
# Format readers -> list[dict]
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # Trim whitespace and drop empty cells so blank columns fall back to defaults.
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        cleaned.append({(k or "").strip(): (v or "").strip()
                        for k, v in row.items() if (k or "").strip()})
    return cleaned


def _read_structured(path: Path, parse) -> list[dict[str, Any]]:
    try:
        data = parse(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise BatchError(f"Failed to parse batch file: {path}",
                         hint="Check the file's syntax.") from exc
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            if key in data:
                data = data[key]
                break
    if not isinstance(data, list):
        raise BatchError("The batch file must be a list of reels.",
                         hint="Provide a top-level list, or a 'reels:' list.")
    return [d for d in data if d is not None]


# --------------------------------------------------------------------------- #
# Normalization + validation
# --------------------------------------------------------------------------- #
def _normalize(row: Any, number: int) -> BatchEntry:
    if not isinstance(row, dict):
        raise BatchError(f"Reel #{number} is not a mapping of fields.",
                         hint="Each entry must have at least a 'prompt'.")

    prompt = str(row.get("prompt", "")).strip()
    if not prompt:
        raise BatchError(f"Reel #{number} has no prompt.",
                         hint="Every entry needs a non-empty 'prompt'.")

    template = row.get("template") or None
    output = row.get("output") or row.get("folder") or row.get("name") or None

    overrides = dict(row.get("overrides") or {})
    flat = {k: v for k, v in row.items() if k not in _ENTRY_KEYS}
    overrides = deep_merge(overrides, _nest_flat(flat, number))

    return BatchEntry(prompt=prompt, template=template, output=output,
                      overrides=overrides)


def _nest_flat(flat: dict[str, Any], number: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in flat.items():
        if value in (None, ""):
            continue
        if key not in _FLAT_FIELDS:
            raise BatchError(f"Reel #{number}: unknown field {key!r}.",
                             hint=f"Known fields: prompt, template, output, "
                                  f"{', '.join(sorted(_FLAT_FIELDS))}.")
        section, name = _FLAT_FIELDS[key]
        coerced = _coerce(name, value)
        out.setdefault(section, {})[name] = coerced
    return out


def _coerce(name: str, value: Any) -> Any:
    if name == "profiles":
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value if str(v).strip()]
        return [p for p in str(value).replace(",", " ").split() if p]
    if name == "gate":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")
    return value


def _reject_duplicates(entries: list[BatchEntry]) -> None:
    seen: dict[str, int] = {}
    for i, entry in enumerate(entries, start=1):
        if entry.name in seen:
            raise BatchError(
                f"Duplicate output folder {entry.name!r} "
                f"(reels #{seen[entry.name]} and #{i}).",
                hint="Give each reel a distinct 'output' (or a distinct prompt).",
            )
        seen[entry.name] = i
