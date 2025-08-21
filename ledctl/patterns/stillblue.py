# Force solid blue by repeatedly resetting RAINBOW at 50 Hz
import time
from ledctl.core import LedCtl, MODE

_RATE_HZ = 50.0
_TICK = 1.0 / _RATE_HZ


def run(
    *,
    port=None,
    baud=10000,
    dtr=True,
    rts=False,
    brightness: int = 1,
    mode_num: int = None,
):
    mode = mode_num if mode_num is not None else MODE.RAINBOW
    with LedCtl(port=port, baud=baud, dtr=dtr, rts=rts, ib_delay=0.001) as ctl:
        try:
            nxt = time.monotonic()
            while True:
                ctl.set_mode_once(mode, brightness, 1)  # speed fixed/ignored
                nxt += _TICK
                dt = nxt - time.monotonic()
                if dt > 0:
                    time.sleep(dt)
        except KeyboardInterrupt:
            pass
    return 0
