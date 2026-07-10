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
    Alarm blink: CYCLE at speed=1, reset every 500 ms -> red/yellow alternating blink.
    """
    # hz dominates here; 2 Hz -> 500 ms
    hz = 2.0 if hz is None else hz
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.CYCLE

    with LedCtl(port=port, baud=baud, ib_delay=ib_delay, dtr=dtr, rts=rts) as ctl:
        try:
            nxt = time.monotonic()
            interval = 1.0 / hz if hz > 0 else 0.5
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                nxt += interval
                time.sleep(max(0, nxt - time.monotonic()))
        except KeyboardInterrupt:
            pass
