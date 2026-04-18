import argparse

from ledctl.cli.off import main as off_main
from ledctl.cli.setmode import main as setmode_main
from ledctl.cli.setpattern import main as pattern_main
from ledctl.cli.wizard import main as wizard_main


def main():
    parser = argparse.ArgumentParser(prog="ledctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("off", help="turn LEDs off")
    sub.add_parser("setmode", help="send a single mode frame or repeat")
    sub.add_parser(
        "pattern",
        help="run a predefined pattern (stillred, stillblue, breathered, alarm)",
    )
    sub.add_parser("wiz", help="interactive curses TUI")

    args, rest = parser.parse_known_args()
    dispatch = {
        "off": off_main,
        "setmode": setmode_main,
        "pattern": pattern_main,
        "wiz": wizard_main,
    }
    dispatch[args.cmd](rest)


if __name__ == "__main__":
    main()
