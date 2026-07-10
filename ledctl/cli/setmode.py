import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.core import LedCtl, MODE, MODES


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setmode",
        description="Send a mode frame (optionally repeat).",
        parents=[make_serial_parser()],
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument(
        "--mode",
        choices=list(MODES),
        help="Named mode",
    )
    g.add_argument("--mode-num", type=lambda x: int(x, 0), help="Raw mode byte (e.g., 0x03)")

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
    p.add_argument("--hz", type=float, default=0.0, help="If >0, repeat at this frequency")
    return p.parse_args(argv)


def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    return MODES.get(args.mode, MODE.CYCLE)


def main(argv=None):
    args = parse_args(argv)
    mode = _resolve_mode(args)
    with LedCtl(
        port=args.port, baud=args.baud, ib_delay=args.ib_delay, dtr=args.dtr, rts=args.rts
    ) as ctl:
        if args.hz and args.hz > 0:
            try:
                while True:
                    ctl.refresh_mode(mode, args.brightness, args.speed, args.hz)
            except KeyboardInterrupt:
                pass
        else:
            ctl.set_mode_once(mode, args.brightness, args.speed)
