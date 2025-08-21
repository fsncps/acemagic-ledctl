# ledctl/__main__.py
import argparse
import sys


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(prog="ledctl", description="LED controller")
    sub = p.add_subparsers(dest="cmd", required=True)

    # NOTE: add_help=False so --help is *not* consumed here.
    sp_off = sub.add_parser("off", help="turn LEDs off (one-shot)", add_help=False)
    sp_off.set_defaults(_entry="ledctl.cli.off:main")

    sp_wiz = sub.add_parser("wiz", help="interactive wizard / helpers", add_help=False)
    sp_wiz.set_defaults(_entry="ledctl.cli.wizard:main")

    sp_setmode = sub.add_parser(
        "setmode", help="set a built-in mode once", add_help=False
    )
    sp_setmode.set_defaults(_entry="ledctl.cli.setmode:main")

    sp_setpattern = sub.add_parser(
        "setpattern",
        help="run a custom pattern (stillred, stillblue, breathered, alarm)",
        add_help=False,
    )
    sp_setpattern.set_defaults(_entry="ledctl.cli.setpattern:main")

    ns, rest = p.parse_known_args(argv)

    modpath, funcname = ns._entry.split(":")
    mod = __import__(modpath, fromlist=[funcname])
    func = getattr(mod, funcname)
    # Pass through remaining args (including --help) to the real subcommand.
    return func(rest)


if __name__ == "__main__":
    raise SystemExit(main())
