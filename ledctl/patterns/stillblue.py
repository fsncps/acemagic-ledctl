import time

from ledctl.core import BAUD_DEFAULT, IB_DELAY_DEFAULT, LedCtl, MODE


def run(
    *,
    port=None,
    baud=BAUD_DEFAULT,
    ib_delay=IB_DELAY_DEFAULT,
    dtr=True,
    rts=False,
    hz: float = None,
    brightness: int = None,
    speed: int = None,
    period: float = None,
    mode_num: int = None,
):
    """
    Force a stable blue/purple by repeatedly resetting RAINBOW (which starts blue/purple).
    Default to 40 Hz like stillred.
    """
    hz = 40.0 if hz is None else hz
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.RAINBOW

    with LedCtl(port=port, baud=baud, ib_delay=ib_delay, dtr=dtr, rts=rts) as ctl:
        try:
            nxt = time.monotonic()
            interval = 1.0 / hz if hz > 0 else 0.0
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                if interval > 0:
                    nxt += interval
                    time.sleep(max(0, nxt - time.monotonic()))
                else:
                    break
        except KeyboardInterrupt:
            pass
