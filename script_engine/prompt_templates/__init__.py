"""Configuration-driven prompt templates (Phase C10)."""
from __future__ import annotations

from script_engine.prompt_templates.registry import (
    PromptTemplate,
    get_template,
    template_names,
)

__all__ = ["PromptTemplate", "get_template", "template_names"]
