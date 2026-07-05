"""Use-case -> engine routing.

Routing chains come from configuration (``routing:`` section), so promoting
a new model after a benchmark round is a YAML edit, not a code change. The
router picks the first adapter in a chain whose optional dependencies are
installed and which satisfies the request's constraints.
"""
from __future__ import annotations

from foundation.constants import Language
from foundation.exceptions import AdapterNotAvailableError, ConfigError
from foundation.logging import get_logger
from foundation.model_manager import Device
from voice_engine.adapters import ADAPTER_CLASSES

logger = get_logger("voice_engine.tts.router")


class EngineRouter:
    """Resolves a use case to a concrete adapter id via configured chains."""

    def __init__(self, chains: dict[str, list[str]]) -> None:
        for use_case, chain in chains.items():
            unknown = [a for a in chain if a not in ADAPTER_CLASSES]
            if unknown:
                raise ConfigError(
                    f"Routing chain {use_case!r} references unknown adapters: {unknown}",
                    use_case=use_case,
                )
        self.chains = chains

    def use_cases(self) -> list[str]:
        return sorted(self.chains)

    def resolve(
        self,
        use_case: str,
        language: Language | None = None,
        require_cloning: bool = False,
    ) -> str:
        """Return the first viable adapter id in the chain for ``use_case``.

        Raises:
            ConfigError: the use case has no configured chain.
            AdapterNotAvailableError: no adapter in the chain is installed
                and capable of the requested language/cloning.
        """
        try:
            chain = self.chains[use_case]
        except KeyError:
            raise ConfigError(
                f"No routing chain configured for use case {use_case!r}",
                known=sorted(self.chains),
            ) from None
        rejected: dict[str, str] = {}
        for adapter_id in chain:
            cls = ADAPTER_CLASSES[adapter_id]
            if require_cloning and not cls.CAPABILITIES.zero_shot_cloning:
                rejected[adapter_id] = "no cloning"
                continue
            if language is not None and language not in cls.CAPABILITIES.languages:
                rejected[adapter_id] = f"no {language.value} support"
                continue
            if not cls(device=Device.CPU).is_available():
                rejected[adapter_id] = "dependencies not installed"
                continue
            logger.debug(
                "Routed use case to engine",
                extra={"context": {"use_case": use_case, "engine": adapter_id}},
            )
            return adapter_id
        raise AdapterNotAvailableError(
            f"No viable engine for use case {use_case!r}",
            use_case=use_case,
            chain=chain,
            rejected=rejected,
        )
