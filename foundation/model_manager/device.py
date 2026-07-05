"""Device resolution for model placement."""
from __future__ import annotations

from enum import Enum

from foundation.logging import get_logger

logger = get_logger("foundation.model_manager.device")


class Device(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"  # Apple Silicon


def resolve_device(requested: Device | str = Device.AUTO) -> Device:
    """Resolve ``auto`` to the best available device.

    Uses ``torch`` when installed; otherwise assumes CPU. Adapters call this
    once at load time so device policy stays consistent platform-wide.
    """
    requested = Device(requested)
    if requested is not Device.AUTO:
        return requested
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return Device.CPU
    if torch.cuda.is_available():
        return Device.CUDA
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return Device.MPS
    return Device.CPU
