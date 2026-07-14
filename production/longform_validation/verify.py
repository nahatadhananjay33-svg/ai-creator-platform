"""Post-download checksum verification.

The download engine records a sha256 for every completed file; this re-hashes
what is on disk and reports files that vanished or no longer match. Read-only —
repair is the engine's job on the next run (a missing file is re-downloaded
because ``_already_have`` requires the file to exist).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from production.media_acquisition.database import MediaDB
from production.media_acquisition.download import sha256
from production.media_acquisition.models import Status


@dataclass
class VerifyReport:
    verified: int = 0
    mismatched: List[str] = field(default_factory=list)   # filename
    missing: List[str] = field(default_factory=list)      # filename

    @property
    def ok(self) -> bool:
        return not self.mismatched and not self.missing


def verify_checksums(db: MediaDB, dest_dir: Path) -> VerifyReport:
    """Re-hash every downloaded file in ``dest_dir`` against the media DB."""
    dest_dir = Path(dest_dir)
    report = VerifyReport()
    for rec in db.all():
        if rec.get("status") != Status.DOWNLOADED.value or not rec.get("filename"):
            continue
        path = dest_dir / rec["filename"]
        if not path.exists():
            report.missing.append(rec["filename"])
        elif rec.get("checksum") and sha256(path) != rec["checksum"]:
            report.mismatched.append(rec["filename"])
        else:
            report.verified += 1
    return report


def _names(names: List[str], cap: int = 5) -> str:
    shown = ", ".join(names[:cap])
    return shown + (", ..." if len(names) > cap else "")


def format_verify(report: VerifyReport) -> str:
    lines = [f"Checksums verified : {report.verified}"]
    if report.missing:
        lines.append(f"Missing files      : {len(report.missing)} ({_names(report.missing)})")
    if report.mismatched:
        lines.append(f"Checksum mismatches: {len(report.mismatched)} ({_names(report.mismatched)})")
    if report.ok:
        lines.append("All downloaded files verified OK.")
    return "\n".join(lines)
