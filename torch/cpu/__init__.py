from typing import Any, Optional, Union
from contextlib import AbstractContextManager
from . import amp
import torch

__all__ = [
    "is_available",
    "synchronize",
    "current_stream",
    "current_stream",
    "stream",
    "device_count",
    "Stream",
]

def _is_cpu_support_vnni() -> bool:
    r"""Returns a bool indicating if CPU supports VNNI."""
    return torch._C._cpu._is_cpu_support_vnni()


def is_available() -> bool:
    r"""Returns a bool indicating if CPU is currently available.

    N.B. This function only exists to facilitate device-agnostic code

    """
    return True

def synchronize(device: Optional[Union[torch.device, int]] = None) -> None:
    r"""Waits for all kernels in all streams on the CPU device to complete.

    Args:
        device (torch.device or int, optional): ignored, there's only one CPU device.

    N.B. This function only exists to facilitate device-agnostic code.
    """
    pass

class Stream:
    """
    N.B. This class only exists to facilitate device-agnostic code
    """
    pass

_default_cpu_stream = Stream()
_current_stream = _default_cpu_stream

def current_stream(device: Optional[Union[torch.device, int]] = None) -> Stream:
    r"""Returns the currently selected :class:`Stream` for a given device.

    Args:
        device (torch.device or int, optional): Ignored.

    N.B. This function only exists to facilitate device-agnostic code

    """
    return _current_stream

class _StreamContext(AbstractContextManager):
    r"""Context-manager that selects a given stream.

    N.B. This class only exists to facilitate device-agnostic code

    """
    cur_stream : Optional[Stream]

    def __init__(self, stream):
        self.stream = stream
        self.prev_stream = _default_cpu_stream

    def __enter__(self):
        cur_stream = self.stream
        if cur_stream is None:
            return

        global _current_stream
        self.prev_stream = _current_stream
        _current_stream = cur_stream

    def __exit__(self, type: Any, value: Any, traceback: Any):
        cur_stream = self.stream
        if cur_stream is None:
            return

        global _current_stream
        _current_stream = self.prev_stream

def stream(stream: Stream) -> AbstractContextManager:
    r"""Wrapper around the Context-manager StreamContext that
    selects a given stream.

    N.B. This function only exists to facilitate device-agnostic code
    """
    return _StreamContext(stream)

def device_count() -> int:
    r"""Returns number of CPU devices (not cores). Always 1.

    N.B. This function only exists to facilitate device-agnostic code
    """
    return 1
