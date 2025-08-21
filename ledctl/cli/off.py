# ledctl/cli/off.py
"""
CLI: turn LEDs off (one-shot).
Examples:
  ledctl off
  ledctl off -p /dev/ttyUSB0 -B 10000 -T -R -d 0.005
"""
from __future__ import annotations

import argparse
from textwrap import dedent

from ledctl.core import set_builtin_mode, BAUD_DEFAULT, IB_DELAY_DEFAULT


def parse_args(argv=None):
    epilog = dedent(
        """\
        Notes:
          • This sends a single OFF frame, then exits.

        Examples:
          ledctl off
          ledctl off -p /dev/ttyUSB0 -B 10000 -T -R -d 0.005
        """
    )
    p = argparse.ArgumentParser(
        prog="ledctl off",
        description="Turn LEDs off (one-shot).",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-p", "--port", help="serial device (auto-detect if omitted)")
    p.add_argument(
        "-B",
        "--baud",
        type=int,
        default=BAUD_DEFAULT,
        help="baud rate (default: %(default)s)",
    )
    p.add_argument(
        "-t", "--dtr", action="store_true", default=True, help="assert DTR (default)"
    )
    p.add_argument(
        "-T", "--no-dtr", dest="dtr", action="store_false", help="deassert DTR"
    )
    p.add_argument("-r", "--rts", action="store_true", default=False, help="assert RTS")
    p.add_argument(
        "-R",
        "--no-rts",
        dest="rts",
        action="store_false",
        help="deassert RTS (default)",
    )
    p.add_argument(
        "-d",
        "--delay",
        type=float,
        default=IB_DELAY_DEFAULT,
        help="inter-byte delay seconds (default: %(default)s)",
    )
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    # brightness/speed are irrelevant for OFF; send a safe default frame
    set_builtin_mode(
        mode="off",
        brightness=1,
        speed=1,
        port=a.port,
        baud=a.baud,
        dtr=a.dtr,
        rts=a.rts,
        ib_delay=a.delay,
    )
    return 0
