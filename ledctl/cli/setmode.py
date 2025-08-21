# ledctl/cli/setmode.py
"""
CLI: set a built-in LED mode once (no loops).
Examples:
  ledctl setmode rainbow
  ledctl setmode cycle -b 1 -s 3
  ledctl setmode breathing -p /dev/ttyUSB0 -B 10000 -t -R -d 0.005
"""
from __future__ import annotations

import argparse
from textwrap import dedent

from ledctl.core import set_builtin_mode, BAUD_DEFAULT, IB_DELAY_DEFAULT

_MODE_CHOICES = ("rainbow", "breathing", "cycle")  # 'off' is its own command


def parse_args(argv=None):
    epilog = dedent(
        """\
        Notes:
          • Brightness/speed are human 1..5 (internally mapped to wire 0x05..0x01).
          • This command is one-shot: sends a single frame and exits.
          • Continuous/custom animations: `ledctl setpattern ...`.

        Examples:
          ledctl setmode rainbow
          ledctl setmode cycle -b 1 -s 3
          ledctl setmode breathing -p /dev/ttyUSB0 -B 10000 -t -R -d 0.005
        """
    )
    p = argparse.ArgumentParser(
        prog="ledctl setmode",
        description="Set a built-in LED mode once (no loops).",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Serial / transport
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

    # Mode + params
    p.add_argument("name", choices=_MODE_CHOICES, help="built-in mode name")
    p.add_argument(
        "-b",
        "--brightness",
        type=int,
        choices=range(1, 6),
        default=1,
        help="brightness 1..5 (default: %(default)s)",
    )
    p.add_argument(
        "-s",
        "--speed",
        type=int,
        choices=range(1, 6),
        default=1,
        help="speed 1..5 (default: %(default)s)",
    )

    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    set_builtin_mode(
        mode=a.name,
        brightness=a.brightness,
        speed=a.speed,
        port=a.port,
        baud=a.baud,
        dtr=a.dtr,
        rts=a.rts,
        ib_delay=a.delay,
    )
    return 0
