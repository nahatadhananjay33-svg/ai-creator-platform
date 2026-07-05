"""Pytest root configuration.

Ensures the repository root is importable so tests can use absolute imports
(``foundation.*``, ``voice_engine.*``) without requiring an editable install.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
