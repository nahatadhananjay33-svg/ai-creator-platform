"""Reel Engine — the platform's orchestration layer.

Turns a declarative Timeline into production-ready social videos. Phase C1
designed the architecture; Phase C2 implements the deterministic walking
skeleton (Timeline IR + renderers + export profiles + benchmark, no AI/GPU).
Generative stages (voice/avatar/caption/templates/branding) arrive in C3+.

Public API lives in the subpackages: ``reel_engine.interfaces`` for the frozen
types, ``reel_engine.timeline`` for the IR, ``reel_engine.render`` for the
renderers. Interfaces follow the platform architecture (docs/ARCHITECTURE.md).
"""
