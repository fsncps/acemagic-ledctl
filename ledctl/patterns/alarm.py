"""
Alarm pattern: bright + slow device speed, periodically reset to cause an obvious blink.
No external loop should touch the serial line.
"""

import time
from ledctl.core import LedCtl, MODE

_TICK = 0.65  # deliberately attention-grabbing; adjust if you want even harsher


def run(
    *,
    port=None,
    baud=10000,
    dtr=True,
    rts=False,
    mode_num: int = None,
):
    mode = mode_num if mode_num is not None else MODE.CYCLE
    with LedCtl(port=port, baud=baud, dtr=dtr, rts=rts, ib_delay=0.005) as ctl:
        try:
            nxt = time.monotonic()
            while True:
                ctl.set_mode_once(mode, brightness=5, speed=5)
                nxt += _TICK
                dt = nxt - time.monotonic()
                if dt > 0:
                    time.sleep(dt)
        except KeyboardInterrupt:
            pass
    return 0
