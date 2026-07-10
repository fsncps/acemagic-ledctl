import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.core import LedCtl, MODES
from ledctl.daemon import kill_running_pattern


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setmode",
        description="Set a built-in LED mode (one-shot).",
        parents=[make_serial_parser()],
    )
    p.add_argument(
        "--mode",
        choices=list(MODES),
        required=True,
        help="Mode to set",
    )
    p.add_argument(
        "--brightness",
        "-b",
        type=int,
        default=3,
        choices=range(1, 6),
        help="1..5 human scale (default 3)",
    )
    p.add_argument(
        "--speed",
        "-s",
        type=int,
        default=3,
        choices=range(1, 6),
        help="1..5 human scale (default 3)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    kill_running_pattern()
    with LedCtl(
        port=args.port, baud=args.baud, ib_delay=args.ib_delay, dtr=args.dtr, rts=args.rts
    ) as ctl:
        ctl.set_mode_once(MODES[args.mode], args.brightness, args.speed)
