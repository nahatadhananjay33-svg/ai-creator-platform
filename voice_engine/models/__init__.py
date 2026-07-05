"""Model catalog for the Voice Engine.

The authoritative metadata lives on each adapter class (``SPEC``); this
package exposes convenient catalog views for reports and docs. Keeping the
spec on the adapter guarantees code and documentation can never diverge.
"""

from voice_engine.models.catalog import all_model_specs, commercial_ready_specs

__all__ = ["all_model_specs", "commercial_ready_specs"]
