# #!/usr/bin/env python3
# # ledctl — ACEMAGIC T9 PLUS LED controller (CH340 @ 10000 baud, 5ms inter-byte)
# # - No args: arrow-key TUI (curses)
# # - Subcommands: set, blink, pulse, list, scan
# #
# # Examples:
# #   ledctl set off
# #   ledctl set breathing -b 5 -s 5          # slow breathing, intense (max bright, slowest)
# #   ledctl set cycle -b 3 -s 1              # fast cycle, medium bright
# #   ledctl blink --a rainbow --b off --on-ms 150 --off-ms 150 --seconds 5
# #   ledctl pulse --mode breathing --seconds 8 --min 2 --max 5 --speed 3
# #
########
#######

import argparse
from ledctl.core import LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setmode", description="Send a mode frame (optionally repeat)."
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--mode", choices=["breath", "cycle", "off", "rainbow"], help="Named mode")
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


def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    if args.mode == "breath":
        return MODE.BREATH
    if args.mode == "cycle":
        return MODE.CYCLE
    if args.mode == "off":
        return MODE.OFF
    if args.mode == "rainbow":
        return MODE.RAINBOW
    # default to cycle if neither given
    return MODE.CYCLE


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
