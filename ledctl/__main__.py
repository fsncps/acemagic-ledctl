import argparse
from ledctl.cli.setmode import main as setmode_main
from ledctl.cli.setpattern import main as pattern_main


def main():
    parser = argparse.ArgumentParser(prog="ledctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setmode", help="send a single mode frame or repeat")
    sub.add_parser(
        "pattern",
        help="run a predefined pattern (stillred, stillblue, breathered, alarm)",
    )

    args, rest = parser.parse_known_args()
    if args.cmd == "setmode":
        setmode_main(rest)
    elif args.cmd == "pattern":
        pattern_main(rest)


if __name__ == "__main__":
    main()
