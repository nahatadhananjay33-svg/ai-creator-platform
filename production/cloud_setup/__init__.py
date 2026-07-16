"""Cloud setup automation for the production voice dataset.

Read-only over the dataset: validates structure + metadata, checksums every file,
emits an upload manifest, and verifies an uploaded copy (e.g. a Drive mount)
against that manifest. Never modifies, rebuilds, trains, or benchmarks.

    python -m production.cloud_setup.prepare
    python -m production.cloud_setup.verify_upload --target <dir>
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
