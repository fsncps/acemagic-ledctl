import argparse
from ledctl.patterns import run_pattern, list_patterns


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="ledctl-pattern", description="Run a predefined pattern.")
    p.add_argument("name", choices=list_patterns(), help="Pattern name")
    p.add_argument("--port", help="Serial device (auto-detect if omitted)")
    p.add_argument("--baud", type=int, default=10000)
    p.add_argument("--dtr", dest="dtr", action="store_true", default=True)
    p.add_argument("--no-dtr", dest="dtr", action="store_false")
    p.add_argument("--rts", dest="rts", action="store_true", default=False)
    p.add_argument("--no-rts", dest="rts", action="store_false")
    # generic knobs many patterns honor:
    p.add_argument("--hz", type=float, default=None, help="Refresh frequency (if applicable)")
    p.add_argument("--brightness", "-b", type=int, default=None, help="1..5 human scale")
    p.add_argument("--speed", "-s", type=int, default=None, help="1..5 human scale")
    p.add_argument(
        "--period",
        type=float,
        default=None,
        help="Seconds for one whole cycle (if applicable)",
    )
    p.add_argument(
        "--mode-num",
        type=lambda x: int(x, 0),
        default=None,
        help="Override the mode byte used by the pattern (advanced)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    run_pattern(
        args.name,
        port=args.port,
        baud=args.baud,
        dtr=args.dtr,
        rts=args.rts,
        hz=args.hz,
        brightness=args.brightness,
        speed=args.speed,
        period=args.period,
        mode_num=args.mode_num,
    )
