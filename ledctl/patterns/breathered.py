# Restart BREATH at preset intervals to keep phase locked on red.
import time
from ledctl.core import LedCtl, MODE

# Presets you measured:
# user s -> (device_speed, brightness, period_seconds)
_PRESETS = {
    1: (1, 4, 5.000),  # s=1  -> dev s=1, b=4, 5000 ms
    2: (2, 3, 4.000),  # s=2  -> dev s=2, b=3, 4000 ms
    3: (3, 2, 3.000),  # s=3  -> dev s=2, b=2, 3000 ms
    4: (4, 1, 1.800),  # s=4  -> dev s=2, b=1, 1800 ms
    5: (5, 1, 1.350),  # s=4  -> dev s=2, b=1, 1800 ms
}


def run(
    *,
    port=None,
    baud=10000,
    dtr=True,
    rts=False,
    # CLI passes speed only for this pattern; brightness is derived from the preset.
    speed: int = 1,
    period: float = None,  # optional manual override for measurement
    mode_num: int = None,
    # brightness from CLI is ignored on purpose (preset defines it)
    **_ignored,
):
    mode = mode_num if mode_num is not None else MODE.BREATH

    dev_speed, preset_brightness, preset_period = _PRESETS.get(speed, _PRESETS[1])
    tick = float(period) if period is not None else preset_period

    with LedCtl(port=port, baud=baud, dtr=dtr, rts=rts) as ctl:
        try:
            # initial kick, then re-send every tick to restart at red
            ctl.set_mode_once(mode, preset_brightness, dev_speed)
            nxt = time.monotonic() + tick
            while True:
                dt = nxt - time.monotonic()
                if dt > 0:
                    time.sleep(dt)
                ctl.set_mode_once(mode, preset_brightness, dev_speed)
                nxt += tick
        except KeyboardInterrupt:
            pass
    return 0
