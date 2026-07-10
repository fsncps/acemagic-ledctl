import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.daemon import (
    daemonize,
    install_sigterm_handler,
    kill_running_pattern,
    remove_pid_file,
    write_pid,
)
from ledctl.patterns import list_patterns, run_pattern


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setpattern",
        description="Run a predefined pattern in the background.",
        parents=[make_serial_parser()],
    )
    p.add_argument(
        "--pattern",
        choices=list_patterns(),
        required=True,
        help="Pattern name",
    )
    p.add_argument("--brightness", "-b", type=int, default=None, help="1..5 human scale")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    kill_running_pattern()
    daemonize()
    write_pid()
    install_sigterm_handler()
    try:
        run_pattern(
            args.pattern,
            port=args.port,
            baud=args.baud,
            ib_delay=args.ib_delay,
            dtr=args.dtr,
            rts=args.rts,
            brightness=args.brightness,
        )
    finally:
        remove_pid_file()
