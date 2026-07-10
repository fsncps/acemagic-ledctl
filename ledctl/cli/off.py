"""CLI: turn LEDs off immediately.

Examples:
  ledctl off
  ledctl off --port /dev/ttyUSB0
"""

import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.core import LedCtl, MODE
from ledctl.daemon import kill_running_pattern


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-off",
        description="Turn LEDs off.",
        parents=[make_serial_parser()],
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    kill_running_pattern()
    with LedCtl(
        port=args.port, baud=args.baud, ib_delay=args.ib_delay, dtr=args.dtr, rts=args.rts
    ) as ctl:
        ctl.set_mode_once(MODE.OFF)
    return 0
