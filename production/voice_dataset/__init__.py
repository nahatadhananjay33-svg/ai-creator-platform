"""Production Voice Dataset Builder.

Turns a folder of the creator's own exported audio/video into a clean,
scored speech dataset — fully local, deterministic, no cloud, no ML, no GPU.

Pipeline (see ``pipeline.py``): ingest -> extract audio -> measure metadata
-> classify content -> detect speech/music/speakers -> score quality ->
accept/reject -> persist (sqlite/csv/xlsx) and route files.

Entry point: ``python -m production.voice_dataset.build``.
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
