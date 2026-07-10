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
    Breathing red: trigger BREATH at speed=1 and reset once per cycle.
    The device starts a breath phase at red; by resetting each cycle-length, it keeps "red breathing".
    Default period ~3.0s (tune to taste/actual hardware).
    """
    # ignore hz for this one; we reset by period
    period = 3.0 if period is None else float(period)
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.BREATH

    with LedCtl(port=port, baud=baud, ib_delay=ib_delay, dtr=dtr, rts=rts) as ctl:
        try:
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                time.sleep(period)
        except KeyboardInterrupt:
            pass
