"""CLI: turn LEDs off immediately.

Examples:
  ledctl off
  ledctl off --port /dev/ttyUSB0
"""

import argparse

from ledctl.core import BAUD_DEFAULT, LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-off",
        description="Turn LEDs off.",
    )
    p.add_argument("--port", help="Serial device (auto-detect if omitted)")
    p.add_argument("--baud", type=int, default=BAUD_DEFAULT)
    p.add_argument("--dtr", dest="dtr", action="store_true", default=True)
    p.add_argument("--no-dtr", dest="dtr", action="store_false")
    p.add_argument("--rts", dest="rts", action="store_true", default=False)
    p.add_argument("--no-rts", dest="rts", action="store_false")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    with LedCtl(port=args.port, baud=args.baud, dtr=args.dtr, rts=args.rts) as ctl:
        ctl.set_mode_once(MODE.OFF)
    return 0
