"""Shared serial-line argument parser used by every subcommand (CR-F1).

Serial flags live on each subcommand's OWN parser via `parents=[serial_parser]`,
never on the top-level parser in __main__.py — otherwise parse_known_args()
would consume them and the subcommand would re-parse an empty rest with its
defaults, silently dropping the user's values.
"""

import argparse

from ledctl.core import BAUD_DEFAULT, IB_DELAY_DEFAULT


def make_serial_parser():
    """Return a parent ArgumentParser carrying the serial-line flags."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--port", help="Serial device (auto-detect if omitted)")
    p.add_argument("--baud", type=int, default=BAUD_DEFAULT, help="Baud rate")
    p.add_argument(
        "--dtr", dest="dtr", action="store_true", default=True, help="Assert DTR (default)"
    )
    p.add_argument("--no-dtr", dest="dtr", action="store_false", help="Deassert DTR")
    p.add_argument("--rts", dest="rts", action="store_true", default=False, help="Assert RTS")
    p.add_argument("--no-rts", dest="rts", action="store_false", help="Deassert RTS (default)")
    p.add_argument(
        "-d",
        "--delay",
        "--ib-delay",
        dest="ib_delay",
        type=float,
        default=IB_DELAY_DEFAULT,
        help="Inter-byte delay, seconds (default %(default)s). The LED micro's "
        "UART drops bytes that arrive back-to-back; bump up for flaky devices, "
        "lower for high-refresh patterns.",
    )
    return p
