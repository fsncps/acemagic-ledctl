# ledctl/core/__init__.py
from .core import (
    LedCtl,
    MODE,
    BUILTIN_MODES,
    BAUD_DEFAULT,
    IB_DELAY_DEFAULT,
    LEVEL_TO_WIRE,
    find_port,
    find_ports,
    checksum,
    build_frame,
    send_frame_one_shot,
)

__all__ = [
    "LedCtl",
    "MODE",
    "BUILTIN_MODES",
    "BAUD_DEFAULT",
    "IB_DELAY_DEFAULT",
    "LEVEL_TO_WIRE",
    "find_port",
    "find_ports",
    "checksum",
    "build_frame",
    "send_frame_one_shot",
    "set_builtin_mode",
    "resolve_mode",
]


def __getattr__(name):
    # Lazy import to avoid circulars: only pull these when actually used.
    if name in ("set_builtin_mode", "resolve_mode"):
        from .setmode import set_builtin_mode, resolve_mode

        return {"set_builtin_mode": set_builtin_mode, "resolve_mode": resolve_mode}[
            name
        ]
    raise AttributeError(name)
