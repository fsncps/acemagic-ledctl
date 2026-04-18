import argparse
from ledctl.core import LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setmode", description="Send a mode frame (optionally repeat)."
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument(
        "--mode",
        choices=["auto", "breath", "cycle", "off", "rainbow"],
        help="Named mode",
    )
    g.add_argument("--mode-num", type=lambda x: int(x, 0), help="Raw mode byte (e.g., 0x03)")

    p.add_argument("--brightness", "-b", type=int, default=3, help="1..5 human scale (default 3)")
    p.add_argument("--speed", "-s", type=int, default=3, help="1..5 human scale (default 3)")
    p.add_argument("--hz", type=float, default=0.0, help="If >0, repeat at this frequency")
    p.add_argument("--port", help="Serial device (auto-detect if omitted)")
    p.add_argument("--baud", type=int, default=10000)
    p.add_argument("--dtr", dest="dtr", action="store_true", default=True)
    p.add_argument("--no-dtr", dest="dtr", action="store_false")
    p.add_argument("--rts", dest="rts", action="store_true", default=False)
    p.add_argument("--no-rts", dest="rts", action="store_false")
    return p.parse_args(argv)


_NAMED_MODES = {
    "auto": MODE.AUTO,
    "breath": MODE.BREATH,
    "cycle": MODE.CYCLE,
    "off": MODE.OFF,
    "rainbow": MODE.RAINBOW,
}


def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    return _NAMED_MODES.get(args.mode, MODE.CYCLE)


def main(argv=None):
    args = parse_args(argv)
    mode = _resolve_mode(args)
    with LedCtl(port=args.port, baud=args.baud, dtr=args.dtr, rts=args.rts) as ctl:
        if args.hz and args.hz > 0:
            try:
                while True:
                    ctl.refresh_mode(mode, args.brightness, args.speed, args.hz)
            except KeyboardInterrupt:
                pass
        else:
            ctl.set_mode_once(mode, args.brightness, args.speed)
