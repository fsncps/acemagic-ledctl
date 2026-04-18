import time

from ledctl.core import LedCtl, MODE


def run(
    *,
    port=None,
    baud=10000,
    dtr=True,
    rts=False,
    hz: float = None,
    brightness: int = None,
    speed: int = None,
    period: float = None,
    mode_num: int = None,
):
    """
    Force solid red by repeatedly resetting CYCLE. Empirically solid at ~40 Hz.
    """
    hz = 40.0 if hz is None else hz
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.CYCLE

    with LedCtl(port=port, baud=baud, dtr=dtr, rts=rts) as ctl:
        try:
            nxt = time.monotonic()
            interval = 1.0 / hz if hz > 0 else 0.0
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                if interval > 0:
                    nxt += interval
                    time.sleep(max(0, nxt - time.monotonic()))
                else:
                    # one-shot (but pattern defaults to continuous)
                    break
        except KeyboardInterrupt:
            pass
