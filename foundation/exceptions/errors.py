"""Exception hierarchy for the AI Creator Platform.

Rules:
- Every platform exception derives from :class:`PlatformError`.
- Engines may subclass these but must never raise bare ``Exception``.
- Exceptions carry structured ``details`` for logging/reporting.
"""
from __future__ import annotations

from typing import Any


class PlatformError(Exception):
    """Base class for all AI Creator Platform errors."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.details:
            extras = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
            return f"{self.message} ({extras})"
        return self.message


class ConfigError(PlatformError):
    """Invalid, missing, or unparseable configuration."""


class CacheError(PlatformError):
    """Cache read/write/integrity failure."""


class ModelError(PlatformError):
    """Base class for model-management and inference errors."""


class ModelNotFoundError(ModelError):
    """Requested model is not registered or its weights are missing."""


class AdapterNotAvailableError(ModelError):
    """Adapter exists but cannot run (no GPU, unsupported platform, ...)."""


class AdapterDependencyError(AdapterNotAvailableError):
    """Adapter's optional Python dependencies are not installed."""

    def __init__(self, adapter: str, packages: tuple[str, ...], **details: Any) -> None:
        super().__init__(
            f"Adapter '{adapter}' requires missing packages: {', '.join(packages)}. "
            f"Install with: pip install {' '.join(packages)}",
            adapter=adapter,
            packages=packages,
            **details,
        )
        self.adapter = adapter
        self.packages = packages


class BenchmarkError(PlatformError):
    """Benchmark orchestration failure."""


class DatasetError(PlatformError):
    """Dataset missing, malformed, or failed validation."""


class EvaluationError(PlatformError):
    """Evaluation framework failure."""


class MetricUnavailableError(EvaluationError):
    """A metric's optional backend (numpy, resemblyzer, ...) is missing."""


class ReportingError(PlatformError):
    """Report generation failure."""
