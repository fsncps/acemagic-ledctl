import argparse

from ledctl.cli.off import main as off_main
from ledctl.cli.pattern_wiz import main as pattern_wiz_main
from ledctl.cli.setmode import main as setmode_main
from ledctl.cli.setpattern import main as pattern_main
from ledctl.cli.wizard import main as wizard_main


def main():
    epilog = """\
Commands:
  ledctl wizard [SERIAL_FLAGS]                      # bare `ledctl` is an alias
  ledctl setmode --mode <mode> [SERIAL_FLAGS] [-b N] [-s N]
  ledctl setpattern --pattern <name> [SERIAL_FLAGS] [-b N]
  ledctl pattern-wiz [SERIAL_FLAGS]
  ledctl off [SERIAL_FLAGS]

Serial flags (after the subcommand): --port, --baud, --dtr/--no-dtr,
--rts/--no-rts, -d/--delay.
"""
    parser = argparse.ArgumentParser(
        prog="ledctl",
        add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("off", help="turn LEDs off", add_help=False)
    sub.add_parser("setmode", help="set a built-in LED mode", add_help=False)
    sub.add_parser("setpattern", help="run a predefined pattern in the background", add_help=False)
    sub.add_parser("pattern-wiz", help="live pattern sequencer TUI", add_help=False)
    sub.add_parser("wiz", help="interactive curses TUI", add_help=False)

    args, rest = parser.parse_known_args()
    dispatch = {
        "off": off_main,
        "setmode": setmode_main,
        "setpattern": pattern_main,
        "pattern-wiz": pattern_wiz_main,
        "wiz": wizard_main,
    }
    if args.cmd is None:
        wizard_main(rest)
    else:
        dispatch[args.cmd](rest)


if __name__ == "__main__":
    main()
