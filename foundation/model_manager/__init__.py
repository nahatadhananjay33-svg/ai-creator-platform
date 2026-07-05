"""Model lifecycle management: specs, registry, device resolution, downloads."""

from foundation.model_manager.spec import ModelSpec, LicenseInfo, HardwareRequirements
from foundation.model_manager.registry import ModelRegistry
from foundation.model_manager.device import Device, resolve_device

__all__ = [
    "ModelSpec",
    "LicenseInfo",
    "HardwareRequirements",
    "ModelRegistry",
    "Device",
    "resolve_device",
]
