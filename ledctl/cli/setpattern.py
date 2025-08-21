# ledctl/cli/setpattern.py
"""
Run a custom LED pattern loop.

Usage:
  ledctl setpattern list
  ledctl setpattern kill
  ledctl setpattern <pattern> [pattern-args] [serial-args] [--background]

Examples:
  ledctl setpattern stillred -b 1
  ledctl setpattern stillblue -b 2
  ledctl setpattern breathered -s 3
  ledctl setpattern alarm --background

Notes:
  • Patterns live in ledctl.patterns.<name> and must expose run(**kwargs).
  • Optional: pattern may expose add_arguments(parser) to register its own CLI.
  • If not provided, we introspect run(...) and add common flags present in its signature:
      -b/--brightness, -s/--speed, --period, --mode-num, --hz
  • By default, starting a new pattern kills existing 'ledctl setpattern' loops.
"""

from __future__ import annotations

import argparse
import inspect
import os
import signal
import subprocess
import sys
from importlib import import_module
from textwrap import dedent

from ledctl.core import BAUD_DEFAULT, IB_DELAY_DEFAULT
from ledctl.patterns import list_patterns, run_pattern


# ---------- process management ----------


def _list_pattern_pids() -> list[int]:
    """Return PIDs for running 'ledctl setpattern' processes (excluding self)."""
    pids: list[int] = []
    me = os.getpid()
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "pid,args"], text=True, errors="ignore"
        )
    except Exception:
        return pids
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("PID"):
            continue
        try:
            pid_str, args = line.split(None, 1)
            pid = int(pid_str)
        except Exception:
            continue
        if pid == me:
            continue
        # Match both "python -m ledctl setpattern ..." and "ledctl setpattern ..."
        if (
            "ledctl" in args
            and " setpattern " in f" {args} "
            and " setpattern kill" not in args
        ):
            pids.append(pid)
    return pids


def kill_all_patterns(grace: float = 0.8) -> int:
    """SIGTERM then SIGKILL all running pattern PIDs. Returns count."""
    pids = _list_pattern_pids()
    if not pids:
        return 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    try:
        import time

        time.sleep(grace)
    except Exception:
        pass
    survivors = _list_pattern_pids()
    for pid in survivors:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    return len(pids)


# ---------- dynamic arg helpers ----------

_COMMON_CANDIDATES = {
    "brightness": dict(
        flags=("-b", "--brightness"),
        kwargs=dict(type=int, choices=range(1, 6), help="brightness 1..5"),
    ),
    "speed": dict(
        flags=("-s", "--speed"),
        kwargs=dict(type=int, choices=range(1, 6), help="speed 1..5"),
    ),
    "period": dict(
        flags=("--period",), kwargs=dict(type=float, help="seconds per cycle")
    ),
    "mode_num": dict(
        flags=("--mode-num",),
        kwargs=dict(
            type=lambda x: int(x, 0), help="override raw MODE byte (e.g., 0x03)"
        ),
    ),
    "hz": dict(flags=("--hz",), kwargs=dict(type=float, help="loop frequency (Hz)")),
}

_SERIAL_GROUP = [
    ("-p", "--port", dict(help="serial device (auto-detect)")),
    (
        "-B",
        "--baud",
        dict(type=int, default=BAUD_DEFAULT, help="baud (default: %(default)s)"),
    ),
    (
        "-t",
        "--dtr",
        dict(action="store_true", default=True, help="assert DTR (default)"),
    ),
    ("-T", "--no-dtr", dict(dest="dtr", action="store_false", help="deassert DTR")),
    ("-r", "--rts", dict(action="store_true", default=False, help="assert RTS")),
    (
        "-R",
        "--no-rts",
        dict(dest="rts", action="store_false", help="deassert RTS (default)"),
    ),
    (
        "-d",
        "--delay",
        dict(
            type=float,
            default=IB_DELAY_DEFAULT,
            help="inter-byte delay seconds (default: %(default)s)",
        ),
    ),
]


def _bind_serial_args(p: argparse.ArgumentParser) -> None:
    for short, longf, kw in _SERIAL_GROUP:
        p.add_argument(short, longf, **kw)


def _pattern_module(name: str):
    return import_module(f".{name}", package="ledctl.patterns")


def _augment_with_pattern_args(p: argparse.ArgumentParser, pattern: str) -> None:
    """Add pattern-specific args from module.add_arguments(parser) or run() signature."""
    mod = _pattern_module(pattern)
    if hasattr(mod, "add_arguments") and callable(getattr(mod, "add_arguments")):
        mod.add_arguments(p)  # type: ignore
        return
    if not hasattr(mod, "run") or not callable(getattr(mod, "run")):
        raise SystemExit(f"Pattern '{pattern}' has no callable run(**kwargs)")
    sig = inspect.signature(mod.run)  # type: ignore
    params = sig.parameters
    for pname, spec in _COMMON_CANDIDATES.items():
        if pname in params:
            flags = spec["flags"]
            kwargs = spec["kwargs"].copy()
            default = params[pname].default
            if default is not inspect._empty:
                kwargs.setdefault("default", default)
                if "help" in kwargs and default is not None:
                    kwargs["help"] += f" (default: {default})"
            p.add_argument(*flags, **kwargs)


def _filter_kwargs_for_run(pattern: str, ns: argparse.Namespace) -> dict:
    """Build kwargs accepted by the pattern's run() from parsed args."""
    mod = _pattern_module(pattern)
    sig = inspect.signature(mod.run)  # type: ignore
    params = sig.parameters

    kv = {
        "port": getattr(ns, "port", None),
        "baud": getattr(ns, "baud", None),
        "dtr": getattr(ns, "dtr", True),
        "rts": getattr(ns, "rts", False),
    }
    kv = {k: v for k, v in kv.items() if k in params}

    for pname in _COMMON_CANDIDATES.keys():
        if pname in params and hasattr(ns, pname):
            kv[pname] = getattr(ns, pname)

    if "ib_delay" in params and hasattr(ns, "delay"):
        kv["ib_delay"] = ns.delay

    return kv


# ---------- parser + main ----------


def _make_base_parser(names: list[str]) -> argparse.ArgumentParser:
    epilog = dedent(
        """\
        Patterns:
          {names}

        Commands:
          list            show available patterns and their accepted arguments
          kill            terminate all running 'ledctl setpattern' loops
          <pattern> ...   run pattern in foreground by default (Ctrl+C to stop),
                          or use --background to detach.

        By default, starting a pattern will kill any existing ledctl setpattern processes.
        """
    ).format(names=", ".join(names))

    p = argparse.ArgumentParser(
        prog="ledctl setpattern",
        description="Run a custom LED pattern (loop lives in the pattern).",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("pattern_or_cmd", nargs="?", help="pattern name or 'list' / 'kill'")
    p.add_argument(
        "--background",
        "-g",
        action="store_true",
        help="run in background (detached); logs to /tmp/ledctl-<pattern>.log",
    )
    p.add_argument(
        "--no-kill-existing",
        action="store_true",
        help="do not terminate existing pattern loops before starting",
    )
    return p


def _print_list(names: list[str]) -> int:
    print("Available patterns:\n")
    for name in names:
        try:
            mod = _pattern_module(name)
            run_sig = inspect.signature(mod.run)  # type: ignore
            params = [
                p
                for p in run_sig.parameters
                if p not in ("port", "baud", "dtr", "rts", "ib_delay")
            ]
            print(f"  {name:12s}  args: {', '.join(params) if params else '(none)'}")
        except Exception as e:
            print(f"  {name:12s}  (error introspecting: {e})")
    print()
    print(
        "Hints: brightness (-b), speed (-s), period (--period), mode_num (--mode-num), hz (--hz)"
    )
    return 0


def _spawn_background(pattern: str, argv_tail: list[str]) -> int:
    """Re-exec ourselves detached, without the --background flag."""
    log = f"/tmp/ledctl-{pattern}.log"
    cmd = [sys.executable, "-m", "ledctl", "setpattern", pattern] + [
        a for a in argv_tail if a not in ("--background", "-g")
    ]
    with open(log, "ab", buffering=0) as fh:
        subprocess.Popen(
            cmd,
            stdout=fh,
            stderr=fh,
            stdin=subprocess.DEVNULL,
            preexec_fn=os.setsid,
            close_fds=True,
        )
    print(f"[ledctl] started pattern '{pattern}' in background (log: {log})")
    return 0


def main(argv=None):
    names = list_patterns()
    base = _make_base_parser(names)

    # First-stage parse (pattern-or-cmd + global flags)
    a, tail = base.parse_known_args(argv)

    # Admin commands
    if not a.pattern_or_cmd or a.pattern_or_cmd == "list":
        return _print_list(names)
    if a.pattern_or_cmd == "kill":
        n = kill_all_patterns()
        print(f"[ledctl] killed {n} pattern process(es)")
        return 0

    # Pattern run
    pattern = a.pattern_or_cmd
    if pattern not in names:
        raise SystemExit(f"Unknown pattern '{pattern}'. Try: ledctl setpattern list")

    # Second-stage parser: pattern-specific + serial flags.
    runner = argparse.ArgumentParser(
        prog=f"ledctl setpattern {pattern}",
        description=f"Run pattern '{pattern}'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    runner.add_argument(
        "--background", "-g", action="store_true", help="run in background (detach)"
    )
    runner.add_argument(
        "--no-kill-existing",
        action="store_true",
        help="do not terminate existing pattern loops before starting",
    )
    _bind_serial_args(runner)
    _augment_with_pattern_args(runner, pattern)

    # IMPORTANT: parse only the tail (everything after the pattern),
    # not the full argv — otherwise 'stillred' appears as an extra arg.
    ns = runner.parse_args(tail)

    if not ns.no_kill_existing:
        kill_all_patterns()

    if ns.background:
        return _spawn_background(pattern, tail)

    kwargs = _filter_kwargs_for_run(pattern, ns)
    try:
        return run_pattern(pattern, **kwargs)
    except KeyboardInterrupt:
        return 0
