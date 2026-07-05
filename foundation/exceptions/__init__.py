"""Platform exception hierarchy."""

from foundation.exceptions.errors import (
    PlatformError,
    ConfigError,
    CacheError,
    ModelError,
    ModelNotFoundError,
    AdapterNotAvailableError,
    AdapterDependencyError,
    BenchmarkError,
    DatasetError,
    EvaluationError,
    MetricUnavailableError,
    ReportingError,
)

__all__ = [
    "PlatformError",
    "ConfigError",
    "CacheError",
    "ModelError",
    "ModelNotFoundError",
    "AdapterNotAvailableError",
    "AdapterDependencyError",
    "BenchmarkError",
    "DatasetError",
    "EvaluationError",
    "MetricUnavailableError",
    "ReportingError",
]
