# CLI_overhaul_ENG.md — Engineering implementation guide

Engineering detail for `CLI_overhaul.md` (CEO-reviewed, authoritative for
decisions). This document is the commit-by-commit "ready to type" guide: real
code blocks, before/after diffs, test specs, failure-mode table.
Branch: `main` | Mode: MEDIUM-TIER CHANGE | Pre-state: 0.3.0, 31 tests green,
ruff clean.

References below use `file:line` and quote the CURRENT tree so each edit is
unambiguous.

---

## Reading order

1. **Decisions / scope** → see `CLI_overhaul.md` (the CEO review lives there).
2. **Dependency graph** → below.
3. **Commit order C1..C8** → below; each commit leaves tree working + tests
   green + ruff clean.
4. **Test specs** → after the commits.
5. **Failure modes** → table at the end.
6. **Completion summary** → final block.

Execution order is **C1 → C2 → C3 → C4 → C5 → C6 → C7 → C8**.
C2/C3 are pure additions (no consumer changes yet). C4 is the first commit
that rewires live consumers. C5 is the biggest (wizard).

---

## Dependency Graph

```
                         ┌──────────────────────┐
                         │      core.py         │  +find_ports() (plural)
                         │      (MODIFY)        │  +MODES + MODE_NAMES
                         │                      │  find_port() delegates
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌─────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
    │ cli/common.py (NEW)  │ │ patterns/*.py    │ │ cli/setmode.py       │
    │ make_serial_parser() │ │ (MODIFY)         │ │ (MODIFY)             │
    │ --port --baud --dtr  │ │ +ib_delay param  │ │ use core.MODES       │
    │ --rts -d/--delay     │ │ +BAUD_DEFAULT    │ │ +choices range(1,6)  │
    └──────────┬──────────┘ │ forward→LedCtl    │ │ breath→breathing     │
               │            └──────────────────┘ └──────────────────────┘
               │ parents=[ ]
               ▼
    ┌────────────────────────────────────────────────────────────┐
    │ off.py   setpattern.py   wizard.py   (each via parents=[)  │
    │ (MODIFY) (MODIFY)        (MODIFY, big)                    │
    └────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   __main__.py (MODIFY) │  NO serial flags at top level (CR-F1)
                    │   minimal subparsers    │  bare → wizard (unchanged)
                    └────────────────────────┘

    ┌─────────────────────┐         ┌──────────────────────────┐
    │ tests/*             │         │ docs/plan/*              │
    │ (MODIFY + conftest) │         │ +TODO +CLI_overhaul      │
    │ per-commit specs    │         │ +CLI_overhaul_ENG        │
    └─────────────────────┘         │ +FIX-COMMANDS (recovered) │
                                    └──────────────────────────┘
```

Data-flow for a serial flag after the overhaul (e.g. `--baud 12000`):

```
user: ledctl off --baud 12000
        │
        ▼
__main__.main():  parser.parse_known_args(["off","--baud","12000"])
        │  top-level has NO --baud (CR-F1) → --baud goes to rest
        ▼
args.cmd="off", rest=["--baud","12000"]
        │
        ▼
off_main(rest):  parse_args(["--baud","12000"])  ← parents=[serial_parser]
        │  serial_parser provides --baud (default BAUD_DEFAULT)
        ▼
args.baud = 12000  ✓  → LedCtl(baud=12000, ...)
```

---

## Commit 1 — C1. chore(infra): un-ignore docs/plan, remove build/ artifact, add plan docs

**Files:** `.gitignore`, `docs/plan/*`, `ledctl/patterns/stillblue.py`

### 1a. `.gitignore` — remove the plan-ignore lines, add `build/`

BEFORE (current `.gitignore`):
```
*/plans/
*/plan/
*.egg-info/
AGENTS.md
```

AFTER (delete the two plan lines; add `build/`):
```
build/
*.egg-info/
AGENTS.md
```

> CR-F2: the `*/plan/` line is what currently hides `docs/plan/` from git.
> Verify after edit:
> ```
> git check-ignore docs/plan/TODO.md   # → exit 1 (no longer ignored)
> git status --short docs/plan/        # → shows the plan files as new
> ```

### 1b. Remove `build/` from disk (untracked — no `git rm`)

```
rm -rf build/
```

`git ls-files | grep -E '^(build|dist)/'` MUST be empty before and after
(verified: build/ is currently `??`, not tracked, so this is a local-only
cleanup).

### 1c. Remove stale comment from `stillblue.py:21`

BEFORE (`ledctl/patterns/stillblue.py:18-22`):
```python
    """
    Force a stable blue/purple by repeatedly resetting RAINBOW (which starts blue/purple).
    Default to 40 Hz like stillred.
    NOTE: Verify MODE.RAINBOW on your device (override with --mode-num if needed).
    """
```

AFTER:
```python
    """
    Force a stable blue/purple by repeatedly resetting RAINBOW (which starts blue/purple).
    Default to 40 Hz like stillred.
    """
```

### 1d. Stage the previously-ignored plan docs into VCS

```
git add docs/plan/TODO.md \
        docs/plan/CLI_overhaul.md \
        docs/plan/CLI_overhaul_ENG.md \
        docs/plan/FIX-COMMANDS-IMPLEMENTATION.md
```

**Why this commit first:** until CR-F2 is fixed, NO plan doc can be committed.
Doing it as C1 makes the whole plan auditable from the start.
**Behaviour change:** none. Pure chore + doc recovery.

---

## Commit 2 — C2. refactor(core): add find_ports() + MODES/MODE_NAMES registry

**Files:** `ledctl/core.py`, `tests/test_core.py`

### 2a. `ledctl/core.py` — add `find_ports()` plural; delegate `find_port()`

BEFORE (`core.py:25-32`):
```python
def find_port() -> Optional[str]:
    """Find the CH340 port deterministically if possible."""
    paths = (
        sorted(glob.glob("/dev/serial/by-path/*-if00-port0"))
        or sorted(glob.glob("/dev/ttyUSB*"))
        or sorted(glob.glob("/dev/ttyACM*"))
    )
    return paths[0] if paths else None
```

AFTER:
```python
def find_ports() -> list:
    """Return all candidate CH340/tty ports, deterministically ordered."""
    return (
        sorted(glob.glob("/dev/serial/by-path/*-if00-port0"))
        or sorted(glob.glob("/dev/ttyUSB*"))
        or sorted(glob.glob("/dev/ttyACM*"))
    )


def find_port() -> Optional[str]:
    """Find a single CH340 port deterministically (first match or None)."""
    return (find_ports() or [None])[0]
```

### 2b. `ledctl/core.py` — add name registry (CR-F4)

Add after the `MODE = SimpleNamespace(...)` / `LEVEL_TO_WIRE` block (after
current line 22):
```python
MODES = {
    "rainbow": MODE.RAINBOW,
    "breathing": MODE.BREATH,
    "cycle": MODE.CYCLE,
    "off": MODE.OFF,
    "auto": MODE.AUTO,
}
MODE_NAMES = list(MODES.keys())
```

> This is the single source of truth for mode name↔value. setmode and wizard
> will both consume it (C5, C6). Today they each keep their own copy, so adding
> the registry now does NOT break anything — no consumer has switched yet.

### 2c. `tests/test_core.py` — extend

Add (do not modify existing tests in C2):
```python
from ledctl.core import find_ports, MODES, MODE_NAMES


def test_find_ports_returns_list():
    result = find_ports()
    assert isinstance(result, list)


def test_find_ports_entries_are_strings():
    for p in find_ports():
        assert isinstance(p, str)


def test_find_port_matches_find_ports_first():
    ports = find_ports()
    assert find_port() == (ports[0] if ports else None)


def test_mode_names_registry():
    assert MODES["rainbow"] == MODE.RAINBOW == 0x01
    assert MODES["breathing"] == MODE.BREATH == 0x02
    assert MODES["cycle"] == MODE.CYCLE == 0x03
    assert MODES["off"] == MODE.OFF == 0x04
    assert MODES["auto"] == MODE.AUTO == 0x05
    assert set(MODE_NAMES) == set(MODES.keys())
```

**Behaviour change:** none. New symbols are unused by consumers yet.
**Test gate:** all green, ruff clean.

---

## Commit 3 — C3. refactor(cli/common): introduce shared serial parent parser

**Files:** NEW `ledctl/cli/common.py`

### Full new file content

```python
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
```

> No `conflict_handler="resolve"` is needed: subcommands inherit these flags
> and do NOT re-declare any of them, so no conflict can arise. (First draft's
> `conflict_handler` note is withdrawn.)

**Behaviour change:** none. Nothing imports this yet.
**Test gate:** all green, ruff clean (new file is imported by no one yet, but
ruff scans it).

---

## Commit 4 — C4. refactor(cli): wire subcommands to parent parser; thread ib_delay (CR-F3)

**Files:** `ledctl/cli/off.py`, `ledctl/cli/setmode.py`,
`ledctl/cli/setpattern.py`, `ledctl/patterns/__init__.py` (no change),
`ledctl/patterns/alarm.py`, `ledctl/patterns/breathered.py`,
`ledctl/patterns/stillred.py`, `ledctl/patterns/stillblue.py`,
`tests/test_cli.py`

### 4a. `ledctl/cli/off.py` — use parent parser; pass ib_delay

BEFORE (`off.py:8-10` + `off.py:13-30`): inline serial args; `main` constructs
`LedCtl(port=..., baud=..., dtr=..., rts=...)` without `ib_delay`.

AFTER:
```python
import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.core import LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-off",
        description="Turn LEDs off.",
        parents=[make_serial_parser()],
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    with LedCtl(port=args.port, baud=args.baud, ib_delay=args.ib_delay,
                dtr=args.dtr, rts=args.rts) as ctl:
        ctl.set_mode_once(MODE.OFF)
    return 0
```

### 4b. `ledctl/cli/setmode.py` — parent parser; add `choices=range(1,6)` (CR-F6)

Keep the `--mode`/`--mode-num` mutex group. Replace the inline serial block
with `parents=[make_serial_parser()]`. Add `choices=range(1,6)` to `-b`/`-s`.

AFTER (full file at this commit — `_NAMED_MODES` and `breath`→`breathing` are
handled in C6; here we keep the local dict for one more commit so C4 stays a
serial-flag-only change):
```python
import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.core import LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-setmode", description="Send a mode frame (optionally repeat).",
        parents=[make_serial_parser()],
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument(
        "--mode",
        choices=["auto", "breath", "cycle", "off", "rainbow"],
        help="Named mode",
    )
    g.add_argument("--mode-num", type=lambda x: int(x, 0), help="Raw mode byte (e.g., 0x03)")
    p.add_argument("--brightness", "-b", type=int, default=3, choices=range(1, 6),
                   help="1..5 human scale (default 3)")
    p.add_argument("--speed", "-s", type=int, default=3, choices=range(1, 6),
                   help="1..5 human scale (default 3)")
    p.add_argument("--hz", type=float, default=0.0, help="If >0, repeat at this frequency")
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
    with LedCtl(port=args.port, baud=args.baud, ib_delay=args.ib_delay,
                dtr=args.dtr, rts=args.rts) as ctl:
        if args.hz and args.hz > 0:
            try:
                while True:
                    ctl.refresh_mode(mode, args.brightness, args.speed, args.hz)
            except KeyboardInterrupt:
                pass
        else:
            ctl.set_mode_once(mode, args.brightness, args.speed)
```

> Choice still says `breath` here deliberately; C6 does the rename so C4 stays
> a serial-flag-only refactor and is easy to review. Add `choices=range(1,6)`
> in C4 because it's a UX-consistency fix tied to the parent-parser work.

### 4c. `ledctl/cli/setpattern.py` — parent parser; forward `ib_delay` (CR-F3)

AFTER:
```python
import argparse

from ledctl.cli.common import make_serial_parser
from ledctl.patterns import run_pattern, list_patterns


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="ledctl-pattern", description="Run a predefined pattern.",
                                 parents=[make_serial_parser()])
    p.add_argument("name", choices=list_patterns(), help="Pattern name")
    p.add_argument("--hz", type=float, default=None, help="Refresh frequency (if applicable)")
    p.add_argument("--brightness", "-b", type=int, default=None, help="1..5 human scale")
    p.add_argument("--speed", "-s", type=int, default=None, help="1..5 human scale")
    p.add_argument("--period", type=float, default=None,
                   help="Seconds for one whole cycle (if applicable)")
    p.add_argument("--mode-num", type=lambda x: int(x, 0), default=None,
                   help="Override the mode byte used by the pattern (advanced)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    run_pattern(
        args.name,
        port=args.port,
        baud=args.baud,
        ib_delay=args.ib_delay,
        dtr=args.dtr,
        rts=args.rts,
        hz=args.hz,
        brightness=args.brightness,
        speed=args.speed,
        period=args.period,
        mode_num=args.mode_num,
    )
```

### 4d. `ledctl/patterns/*.py` — add `ib_delay` to each `run()`; use `BAUD_DEFAULT`

Each pattern's `run()` gains an `ib_delay` keyword and forwards it to `LedCtl`.
The `baud=10000` literal becomes `baud=BAUD_DEFAULT` (imported).

Template (alarm.py shown; same shape for the other three, differing only in
defaults and mode):
```python
import time

from ledctl.core import BAUD_DEFAULT, IB_DELAY_DEFAULT, LedCtl, MODE


def run(
    *,
    port=None,
    baud=BAUD_DEFAULT,
    ib_delay=IB_DELAY_DEFAULT,
    dtr=True,
    rts=False,
    hz: float = None,
    brightness: int = None,
    speed: int = None,
    period: float = None,
    mode_num: int = None,
):
    """
    Alarm blink: CYCLE at speed=1, reset every 500 ms -> red/yellow alternating blink.
    """
    hz = 2.0 if hz is None else hz
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.CYCLE

    with LedCtl(port=port, baud=baud, ib_delay=ib_delay, dtr=dtr, rts=rts) as ctl:
        try:
            nxt = time.monotonic()
            interval = 1.0 / hz if hz > 0 else 0.5
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                nxt += interval
                time.sleep(max(0, nxt - time.monotonic()))
        except KeyboardInterrupt:
            pass
```

Apply the same `ib_delay=IB_DELAY_DEFAULT` insertion to `breathered.py`,
`stillred.py`, `stillblue.py`. `stillblue.py` also gets the comment removal
(BUT the comment removal is already done in C1 — do not touch it again).

### 4e. `tests/test_cli.py` — update serial-flag coverage

Add (existing mode tests unchanged in C4):
```python
def test_off_parse_args_has_delay_default():
    args = off_parse_args([])
    assert args.ib_delay == 0.005


def test_off_parse_args_delay_flag():
    args = off_parse_args(["--delay", "0.008"])
    assert args.ib_delay == 0.008


def test_off_parse_args_ib_delay_alias():
    args = off_parse_args(["--ib-delay", "0.002"])
    assert args.ib_delay == 0.002


def test_setmode_parse_args_has_baud_default():
    args = parse_args([])            # setmode.parse_args
    assert args.baud == 10000


def test_setmode_brightness_choices_rejects_bad():
    # argparse raises SystemExit on choices=range(1,6) violation
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["-b", "9"])


def test_setpattern_parse_args_ib_delay():
    from ledctl.cli.setpattern import parse_args as sp_parse_args
    args = sp_parse_args(["alarm", "--delay", "0.003"])
    assert args.ib_delay == 0.003


def test_setpattern_parse_args_forwards_ib_delay():
    # spot-check that main() would pass ib_delay through (mock run_pattern)
    from unittest.mock import MagicMock
    import ledctl.cli.setpattern as sp
    mock = MagicMock()
    sp.run_pattern = mock
    args = sp.parse_args(["alarm", "--delay", "0.004"])
    # simulate main flow without hardware:
    sp.main(["alarm", "--delay", "0.004"])
    _, kwargs = mock.call_args
    assert kwargs.get("ib_delay") == 0.004
```

> Some of the above monkeypatch module globals; ensure the tests restore them
> (use `monkeypatch` fixture in the real suite rather than direct assignment).

**Behaviour change:** `off`/`setmode`/`setpattern` now honour `--delay`; bad
brightness on setmode is rejected by argparse. No invocation that previously
worked is broken.
**Test gate:** all green, ruff clean.

---

## Commit 5 — C5. refactor(wizard): import from core; make TUI-only

**Files:** `ledctl/cli/wizard.py`, `ledctl/__main__.py`, `tests/test_cli.py`

This is the largest commit. The wizard stops being a parallel mini-library.

### 5a. `ledctl/cli/wizard.py` — strip duplicates, import from core

DELETE from `wizard.py` (current lines as labeled):
- `import glob` (line 2) — no longer used (find_ports now in core)
- `import serial` + try/except (lines 6-9) — LedCtl owns serial now
- `BAUD`, `IB_DELAY` (lines 11-12)
- `MODES`, `MODE_NAMES`, `LEVEL_TO_WIRE` (lines 15-29)
- `find_ports()`, `checksum()`, `send_frame()` (lines 32-55)

ADD at top:
```python
import argparse
import sys
import time

from ledctl.cli.common import make_serial_parser
from ledctl.core import (
    BAUD_DEFAULT, IB_DELAY_DEFAULT, LEVEL_TO_WIRE, LedCtl,
    MODE, MODES, MODE_NAMES, find_ports,
)
```

### 5b. Drop the wizard subcommands (CR via M1.4)

DELETE in `parse_args()`:
- the `-d/--dev` arg (line 78) — replaced by `--port` from the parent parser
- the `--dtr/--no-dtr/--rts/--no-rts/--delay` top-level args (lines 80-94)
  — now inherited from the parent parser
- the entire `sub = p.add_subparsers(dest="cmd")` block and all
  `set`/`blink`/`pulse`/`list`/`scan` subparsers (lines 96-143)

DELETE in `main()`:
- the `if a.cmd == "list"/"set"/"blink"/"pulse"` branches (lines 334-380)
- the `find_ports()[0]` eager pick (line 332)

### 5c. New minimal `wizard.parse_args()` and `main()`

```python
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-wizard",
        description="Interactive curses TUI for the ACEMAGIC LED controller.",
        parents=[make_serial_parser()],
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    tui(args.port, args.dtr, args.rts, args.ib_delay)
    return 0
```

### 5d. Refactor `tui()` to hold one `LedCtl`; recreate on port change (CR-F7)

New structure — replaces the `send_frame(...)` calls with `ctl.set_mode_once`
and recreates the `LedCtl` when the port field is changed:

```python
def tui(dev, dtr, rts, delay):
    try:
        import curses
    except Exception:
        print("curses not available; falling back to text mode.")
        return text_interactive(dev, dtr, rts, delay)

    ports = find_ports()
    if not ports:
        print("No CH340 tty found.")
        return
    port_idx = 0 if dev is None else (ports.index(dev) if dev in ports else 0)

    mode_idx = MODE_NAMES.index("off")
    bright = 3
    speed = 3
    _dtr, _rts = dtr, rts

    def make_ctl():
        # Explicit port avoids LedCtl's find_port(); no SystemExit on missing device.
        return LedCtl(port=ports[port_idx], baud=BAUD_DEFAULT, ib_delay=delay,
                      dtr=_dtr, rts=_rts)

    ctl = make_ctl()
    ctl.open()

    def apply():
        ctl.set_mode_once(MODES[MODE_NAMES[mode_idx]], bright, speed)

    def off():
        ctl.set_mode_once(MODES["off"], bright, speed)

    def blink_test():
        ctl.set_mode_once(MODES["rainbow"], 5, 2)
        time.sleep(0.2)
        ctl.set_mode_once(MODES["off"], 3, 3)

    def on_port_change(step):
        nonlocal port_idx, ctl
        ports[:] = find_ports() or ports
        if not ports:
            return
        port_idx = (port_idx + step) % len(ports)
        ctl.close()
        ctl = make_ctl()
        ctl.open()

    idx = 1  # start at Mode

    # ... bold_if/draw unchanged except they reference ports[]/MODE_NAMES as now

    def main(stdscr):
        nonlocal idx, port_idx, mode_idx, bright, speed, _dtr, _rts
        curses.curs_set(0)
        draw(stdscr)
        while True:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                off()
                break
            elif key == curses.KEY_UP:
                idx = (idx - 1) % 10
            elif key == curses.KEY_DOWN:
                idx = (idx + 1) % 10
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                step = -1 if key == curses.KEY_LEFT else 1
                if idx == 0:           # Port
                    on_port_change(step)
                elif idx == 1:         # Mode
                    mode_idx = (mode_idx + step) % len(MODE_NAMES)
                elif idx == 2:         # Brightness
                    bright = min(5, max(1, bright + step))
                elif idx == 3:         # Speed
                    speed = min(5, max(1, speed + step))
                elif idx == 4:         # DTR
                    _dtr = not _dtr
                elif idx == 5:         # RTS
                    _rts = not _dts
            elif key in (curses.KEY_ENTER, 10, 13):
                if idx == 6:
                    apply()
                elif idx == 7:
                    off()
                elif idx == 8:
                    blink_test()
                elif idx == 9:
                    off()
                    ctl.close()
                    return
                else:
                    apply()
            elif key in (ord("a"), ord("A")):
                apply()
            elif key in (ord("o"), ord("O")):
                off()
            elif key in (ord("b"), ord("B")):
                blink_test()
            draw(stdscr)

    try:
        curses.wrapper(main)
    finally:
        ctl.close()
```

> Note in the snippet: the `_rts = not _dts` line is a typo placeholder — in
> the real edit use `_rts = not _rts`. Keep `draw()` and `bold_if()` unchanged
> from the current wizard (they only read `ports[]`, `MODE_NAMES`, `bright`,
> `speed`, `_dtr`, `_rts`, `idx`). The `apply()/off()/blink_test()` now use the
> held `ctl`.
> Port-switch mechanism (CR-F7): we recreate the `LedCtl` rather than add a
> `reopen()` API — less core surface.

### 5e. `text_interactive()` — same treatment (simpler)

It already lacked the curses loop; convert its `send_frame(...)` calls to a
single held `LedCtl` built once. No port-switcher exists in text mode, so no
recreate logic needed. Replace the body's `send_frame(port, MODES["off"], ...)`
patterns with `ctl.set_mode_once(MODES["off"], ...)`.

### 5f. `ledctl/__main__.py` — stays minimal (CR-F1)

No serial flags on the top-level parser. Keep current shape; only update help
text and the `setpattern` help to be generic.

BEFORE (`__main__.py`):
```python
sub.add_parser("pattern",
    help="run a predefined pattern (stillred, stillblue, breathered, alarm)")
```
AFTER:
```python
sub.add_parser("pattern", help="run a predefined pattern (see --help for the list)")
```

Full after-state of `__main__.py` (the top-level parser deliberately has NO
`parents=[make_serial_parser()]` — CR-F1):
```python
import argparse

from ledctl.cli.off import main as off_main
from ledctl.cli.setmode import main as setmode_main
from ledctl.cli.setpattern import main as pattern_main
from ledctl.cli.wizard import main as wizard_main


def main():
    parser = argparse.ArgumentParser(prog="ledctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("off", help="turn LEDs off")
    sub.add_parser("setmode", help="send a single mode frame or repeat")
    sub.add_parser("pattern", help="run a predefined pattern (see --help for the list)")
    sub.add_parser("wizard", help="interactive curses TUI")

    args, rest = parser.parse_known_args()
    dispatch = {
        "off": off_main,
        "setmode": setmode_main,
        "pattern": pattern_main,
        "wizard": wizard_main,
    }
    if args.cmd is None:
        wizard_main(rest)
    else:
        dispatch[args.cmd](rest)


if __name__ == "__main__":
    main()
```

> Register an explicit `wizard` subcommand name (previously only `wiz`). The
> README references `ledctl wiz`; keep `wiz` as an alias by registering both
> `wiz` and `wizard` pointing to `wizard_main` — optional polish, do in C7
> with the README pass if desired. Here we keep `wiz` to avoid a CLI-name
> break in C5; the CEO doc uses `wizard` as the canonical name.

### 5g. `tests/test_cli.py` — drop obsolete wizard tests, add new (CR-F13)

DELETE:
- `test_wiz_scan_parse_args`
- `test_wiz_set_parse_args`
- `test_wiz_main_accepts_argv` (tested `["list"]` which is gone)

ADD:
```python
def test_wiz_parse_args_defaults():
    from ledctl.cli.wizard import parse_args
    args = parse_args([])
    assert args.ib_delay == 0.005
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False
    assert args.port is None


def test_wiz_parse_args_rejects_old_subcommand(monkeypatch):
    import pytest
    from ledctl.cli.wizard import parse_args
    with pytest.raises(SystemExit):
        parse_args(["set", "off"])     # 'set' no longer exists


def test_wiz_main_calls_tui(monkeypatch):
    import ledctl.cli.wizard as w
    called = {}
    def fake_tui(port, dtr, rts, delay):
        called["args"] = (port, dtr, rts, delay)
    monkeypatch.setattr(w, "tui", fake_tui)
    rc = w.main(["--baud", "12000"])
    assert rc == 0
    assert called["args"][1] is True   # dtr default
```

The existing `test_main_no_args_defaults_to_wiz` still passes (bare `ledctl`
→ `wizard_main(rest)`).

**Behaviour change:** `ledctl wiz set/blink/pulse/list/scan` no longer work
(the README quickstart never advertised them). `ledctl wiz` and bare `ledctl`
launch the curses TUI exactly as before. `-d/--dev` is gone (→ `--port`).
**Test gate:** all green, ruff clean. Smoke: `python -c "import ledctl.cli.wizard"`.

---

## Commit 6 — C6. refactor(setmode): consume core.MODES; hard-rename breath → breathing

**Files:** `ledctl/cli/setmode.py`, `tests/test_cli.py`, `tests/conftest.py` (NEW)

### 6a. `ledctl/cli/setmode.py` — drop `_NAMED_MODES`; use `core.MODES`

BEFORE (after C4):
```python
from ledctl.core import LedCtl, MODE
...
g.add_argument("--mode", choices=["auto", "breath", "cycle", "off", "rainbow"], ...)
...
_NAMED_MODES = {"auto": MODE.AUTO, "breath": MODE.BREATH, ...}
def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    return _NAMED_MODES.get(args.mode, MODE.CYCLE)
```

AFTER:
```python
from ledctl.core import LedCtl, MODE, MODES
...
g.add_argument("--mode", choices=list(MODES), help="Named mode")
...
def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    return MODES.get(args.mode, MODE.CYCLE)
```

Because `core.MODES` already uses key `"breathing"` (added in C2), `--mode`
now accepts `breathing` and rejects `breath`. No alias.

### 6b. `tests/test_cli.py` — rename `breath` tests

```python
def test_resolve_mode_breathing():
    args = parse_args(["--mode", "breathing"])
    assert _resolve_mode(args) == MODE.BREATH


def test_parse_args_breathing():
    args = parse_args(["--mode", "breathing"])
    assert args.mode == "breathing"


def test_parse_args_breath_rejected():
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["--mode", "breath"])   # hard rename, no alias
```

Delete the old `test_resolve_mode_breath` / `test_parse_args_with_mode` cases
that used `breath`, or retarget them to `breathing`.

### 6c. `tests/conftest.py` (NEW) — registry tripwire (CR-F4)

```python
from ledctl.core import MODE, MODES


def test_mode_names_match_constants():
    assert MODES["rainbow"] == MODE.RAINBOW
    assert MODES["breathing"] == MODE.BREATH
    assert MODES["cycle"] == MODE.CYCLE
    assert MODES["off"] == MODE.OFF
    assert MODES["auto"] == MODE.AUTO
```

> Guards against re-introducing a second source of truth for the name↔value
> map — the exact bug class that RAINBOW fell into.

**Behaviour change:** `--mode breath` rejected (use `breathing`).
**Test gate:** all green, ruff clean.

---

## Commit 7 — C7. chore(docs): document bare-ledctl default & help epilog; CHANGELOG

**Files:** `README.md`, `ledctl/__main__.py` (epilog), `CHANGELOG.md`

### 7a. README "Quick start" — note bare-ledctl + post-subcommand flags
Add a note near the Quick start section:
```
Running `ledctl` with no subcommand launches the interactive curses TUI
(same as `ledctl wiz`). Serial flags go *after* the subcommand:
`ledctl off --baud 12000`, not `ledctl --baud 12000 off`.
```

### 7b. `__main__.py` — top-level epilog
Add an `epilog=` to the top-level `ArgumentParser`:
```python
epilog="""\
Commands:
  ledctl wizard [SERIAL_FLAGS]        # bare `ledctl` is an alias
  ledctl setmode  <mode> [SERIAL_FLAGS] [-b N] [-s N] [--hz HZ]
  ledctl setpattern <pattern> [SERIAL_FLAGS] [-b N] [-s N] [--period SEC]
  ledctl off [SERIAL_FLAGS]
"""
```
with `formatter_class=argparse.RawDescriptionHelpFormatter`.

### 7c. `CHANGELOG.md`
```markdown
## [0.4.0] - UNRELEASED

### Removed
- Wizard subcommands `set`/`blink`/`pulse`/`list`/`scan` — `set` is now `ledctl setmode`;
  the others were non-documented extras. `ledctl wiz`/bare `ledctl` still launch the TUI.
- `--mode breath` (use `breathing`). No alias.
- Wizard's `-d`/`--dev` (use `--port`).

### Changed
- Mode-name vocabulary standardised on `breathing` everywhere.
- All subcommands now honour `--delay` (inter-byte delay); previously only the wizard did.
- Serial flags (`--port`, `--baud`, `--dtr/--no-dtr`, `--rts/--no-rts`, `-d/--delay`)
  are now shared via a single parent parser; no duplication.
- Wizard `-d` now means `--delay` (matches README), not device.
- Mode registry centralised in `ledctl.core` (`MODE` namespace + `MODES` dict + `MODE_NAMES`).

### Added
- `ledctl.core.find_ports()` (plural) and `MODES`/`MODE_NAMES` name registry.
```

**Test gate:** no test changes (docs); still run pytest + ruff to be safe.

---

## Commit 8 (optional) — C8. chore(version): bump to 0.4.0

**Files:** `ledctl/__init__.py`, `pyproject.toml`

```python
# ledctl/__init__.py
__version__ = "0.4.0"
```
```toml
# pyproject.toml
version = "0.4.0"
```
Finalise the CHANGELOG date when tagging. Open decision (CR-F12) — skip if the
maintainer prefers to stay on 0.3.x.

---

## Test specs per commit

```
COMMIT  FILE                        NEW CODEPATH                         TYPE
C1      stillblue.py                comment removed                       (no code path)
C1      .gitignore                  docs/plan un-ignored                  git check-ignore(1)
C2      core.py                     find_ports() returns list             unit
C2      core.py                     find_port() == find_ports()[0]        unit
C2      core.py                     MODES/MODE_NAMES registry             unit
C3      cli/common.py              make_serial_parser() exposes flags     unit (via C4 tests)
C4      off.py                      ib_delay reached in LedCtl            unit
C4      setmode.py                  --baud inherited; -b choices=1..5    unit
C4      setpattern.py               ib_delay forwarded to run_pattern    unit (mock)
C4      patterns/*.py               ib_delay forwarded to LedCtl         import + signature
C5      wizard.py                   tui() uses LedCtl context            unit (mock tui)
C5      wizard.py                   parse_args rejects old subcommands   unit (SystemExit)
C5      __main__.py                 bare → wizard                         existing test
C6      setmode.py                  --mode breathing; breath rejected     unit
C6      conftest.py                 MODES↔MODE tripwire                   unit
C7/C8   docs/changelog              n/a                                   (docs)

NOT TESTED (require hardware or curses):
  - Live serial writes via LedCtl.set_mode_once()
  - curses TUI render/keyloop (C5 mocks tui)
  - Pattern run() infinite loops with a real device
```

---

## Failure modes

| Codepath                                                  | Failure                       | Handled?   | Test?   | User sees                                                |
|-----------------------------------------------------------|-------------------------------|------------|---------|----------------------------------------------------------|
| `ledctl off --baud 12000`                                 | Previously ignored            | FIXED C4   | YES C4  | Flag actually applied to transport                       |
| `ledctl setpattern alarm --delay 0.002`                   | Previously dropped            | FIXED C4   | YES C4  | Pattern uses 2 ms inter-byte delay                       |
| `ledctl setmode -b 9`                                     | Late ValueError               | FIXED C4   | YES C4  | argparse error "invalid choice"                         |
| `ledctl --baud 12000 off` (flag before sub)               | argparse misbinds to `cmd`    | EXISTING   | N/A     | "invalid choice: '12000'" — documented post-sub UX       |
| `ledctl wiz set/blink/...` (old wizard subcommands)       | Gone                          | FIXED C5   | YES C5  | argparse error (subcommand unknown)                      |
| `ledctl wiz -d /dev/ttyUSB0` (old wizard device short)    | Now interpreted as --delay    | BY-DES C5  | (docs)  | `--help` shows `-d=--delay`; README updated (C7)         |
| `ledctl setmode --mode breath`                             | Renamed                       | FIXED C6   | YES C6  | argparse "invalid choice"; use `breathing`              |
| Serial flag set on top-level parser (regression)          | Would consume & drop value    | PREVENT    | YES*    | Enforced by C5 keeping top-level minimal; conftest guard |
| `docs/plan/*.md` not tracked                               | Ignored by `*/plan/`          | FIXED C1   | YES C1  | `git check-ignore` returns non-zero                      |
| `core.MODES` drifts from `core.MODE`                       | Two registry sources          | GUARD C6   | YES C6  | conftest tripwire catches it at test time                |
| No CH340 plugged in                                       | SystemExit from LedCtl        | EXISTING   | N/A     | "No CH340 tty found"                                     |
| Pattern module import error                                | Raw ImportError               | ACCEPTED   | N/A     | Development-time error (documented)                      |

\* The "no serial flags at top level" rule is enforced by C5 leaving
`__main__.py` minimal AND by the visible-before/after diff, not by a runtime
test — a reviewer must watch the `__main__.py` diff in C5.

---

## Verification gates (per commit)

After each commit:
1. `python -m pytest -q` — all green.
2. `python -m ruff check ledctl tests` — clean.
3. `python -c "import ledctl.__main__; import ledctl.cli.wizard"`.

After C1 also:
4. `git check-ignore docs/plan/TODO.md` exits non-zero (file tracked).
5. `git ls-files | grep -E '^(build|dist)/'` empty.

After C4 also:
6. `ledctl off --help` shows `--delay` and the serial-flag group once.
7. `ledctl setmode --help` shows `choices=range(1,6)` on `-b`/`-s`.
8. `ledctl setpattern --help` shows `--delay`.

After C5 also:
9. `ledctl --help` does NOT show `--baud`/`--port` at the top level (CR-F1).
10. `ledctl wiz set` errors (SystemExit); `ledctl wiz` still launches TUI
    (manual/skip in CI).
11. `ledctl` (bare) still routes to wizard (existing unit test holds).

After C6 also:
12. `ledctl setmode --mode breathing` accepted; `--mode breath` rejected.

After C7:
13. `ledctl --help` shows the epilog with the four command forms.

Final tree state: `git ls-files | grep -E '^(build|dist)/'` empty;
`docs/plan/` tracked; 0.4.0 (if C8) across `__init__.py` + `pyproject.toml` +
`CHANGELOG.md`.

---

## ENG notes (non-blocking but worth knowing)

- **Argparse `parents=` copies arguments, it does not share.** Each subcommand
  gets its own copy of the serial flags — that's fine (independent parsers).
  Defaults come along; a subcommand can't accidentally mutate the parent.
- **`LedCtl.__init__` with an explicit `port` skips `find_port()`**, so the
  wizard's `make_ctl(port=ports[port_idx], ...)` does NOT raise on a missing
  device even if the port list was refreshed to the current plugged adapter.
- **`LedCtl` does not auto-open** — `__enter__`/`open()` is explicit. The
  wizard's `make_ctl()` + `ctl.open()` mirrors that; `ctl.close()` is called
  in `finally` and on quit.
- **`run_pattern(**kwargs)` already passes kwargs through** to `mod.run(**kwargs)`,
  so `ib_delay=args.ib_delay` added in setpattern's `main()` reaches each
  pattern's `run()` automatically once those signatures accept it (C4).
- **`__main__.py` switching from `if/elif` to dict dispatch was already done**
  in 0.3.0; this overhaul keeps it.
- **`requirements-python = ">=3.8"`** — the new `list` lowercase generic in the
  `find_ports()` return annotation is a *comment* (no `from __future__ import
  annotations`), but it's only an annotation and 3.8 tolerates `list[...]` in
  annotations? No — `list[str]` as a runtime annotation needs 3.9+. The C2
  code block uses `def find_ports() -> list:` (bare `list`) to stay 3.8-safe.
  Do NOT use `list[str]` in the runtime type of the function definition.
- **`conflict_handler="resolve"`** NOT needed — verified: no subcommand
  re-declares a serial flag. (Was a first-draft concern; withdrawn in CEO review.)

---

## NOT in scope (cross-references)

- Broken README doc links (TODO M5.1) — defer.
- `--background`/`--no-kill-existing` (TODO CR-F11/M5) — recommend README removal.
- Device-model P9/T9 naming (TODO CR-F10/M5).

## What already exists (reused, not rebuilt)

| Component | File | Reused how |
|-----------|------|------------|
| Serial framing / `LedCtl` | `core.py` | wizard now calls `set_mode_once` instead of its own `send_frame` |
| Port detection | `core.find_ports/find_port` | wizard + every subcommand |
| Mode constants | `core.MODE` | unchanged; new `MODES`/`MODE_NAMES` derived from it |
| Pattern auto-discovery | `patterns/__init__.py` | unchanged; `ib_delay` flows through `**kwargs` |
| Console scripts | `pyproject.toml` | `ledctl-wizard` still maps to `wizard.main`; behaviour narrows |
| Argparse per-subcommand shape | existing `off.py` | the new `common.make_serial_parser()` factors out only the shared part |

---

## Completion Summary

```
+========================================================================+
|                  ENG REVIEW — CLI OVERHAUL                             |
+========================================================================+
| Step 0               | MEDIUM-TIER CHANGE — eng-detail review           |
| CEO review           | 13 findings; 2 blockers + 2 high corrected       |
| Architecture review  | CR-F1 (parsing) + CR-F2 (gitignore) blockers     |
| Code quality review  | CR-F3 (ib_delay thread) + CR-F4 (MODES central)  |
| Test review          | per-commit specs + conftest tripwire + mock-tui   |
| Performance review   | no changes – purely structural                    |
+------------------------------------------------------------------------+
| Commits              | 8 (C8 optional version bump)                      |
| Files modified       | core, off, setmode, setpattern, wizard, __main__   |
| Files added          | cli/common.py, conftest.py                        |
| Files deleted        | none (build/ removed locally, untracked)           |
| Breaking changes     | wizard subcommands, breath→breathing, wizard -d    |
| Open decisions       | 2 (version bump; CR-F7 chosen=recreate)            |
| Failure modes mapped | 11 (0 critical gaps after C1..C6/C7)               |
+========================================================================+
```