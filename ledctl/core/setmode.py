# ledctl/core/setmode.py  (LIBRARY — no package-level imports)
from __future__ import annotations
from typing import Optional, Union

from .core import (  # <- RELATIVE import is critical
    BUILTIN_MODES,
    BAUD_DEFAULT,
    IB_DELAY_DEFAULT,
    send_frame_one_shot,
)


def resolve_mode(mode: Union[str, int]) -> int:
    if isinstance(mode, int):
        return mode
    key = str(mode).lower()
    if key in BUILTIN_MODES:
        return BUILTIN_MODES[key]
    raise SystemExit(f"Unknown mode '{mode}'. Valid: {', '.join(BUILTIN_MODES)}")


def set_builtin_mode(
    *,
    mode: Union[str, int],
    brightness: int = 3,
    speed: int = 3,
    port: Optional[str] = None,
    baud: int = BAUD_DEFAULT,
    dtr: bool = True,
    rts: bool = False,
    ib_delay: float = IB_DELAY_DEFAULT,
) -> None:
    mode_byte = resolve_mode(mode)
    if brightness not in (1, 2, 3, 4, 5) or speed not in (1, 2, 3, 4, 5):
        raise SystemExit("brightness/speed must be in 1..5")
    send_frame_one_shot(
        port=port,
        mode=mode_byte,
        brightness=brightness,
        speed=speed,
        baud=baud,
        dtr=dtr,
        rts=rts,
        ib_delay=ib_delay,
    )
