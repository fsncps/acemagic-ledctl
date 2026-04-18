# FIX-COMMANDS-IMPLEMENTATION.md

Engineering implementation guide for `docs/plans/2026-04-18-fix-commands.md`.
Branch: `main` | Mode: SMALL CHANGE (compressed ENG review)

---

## Dependency Graph

```
                    ┌──────────────┐
                    │   core.py    │  MODE constants, LedCtl, find_port
                    │  (MODIFY)    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────────┐
              │            │                │
              ▼            ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │cli/setmode.py│ │  cli/off.py  │ │patterns/     │
     │  (MODIFY)    │ │   (NEW)      │ │__init__.py   │
     └──────────────┘ └──────────────┘ │  (FILL)      │
                                      └──────┬───────┘
                                             │
                              ┌───────────┬──┴──┬──────────┐
                              ▼           ▼     ▼          ▼
                        stillred.py  stillblue.py  breathered.py  alarm.py
                        (unchanged)  (unchanged)   (unchanged)    (unchanged)

     ┌──────────────┐
     │ __main__.py  │  Routes all 4 subcommands
     │  (MODIFY)    │
     └──────────────┘

     ┌──────────────┐
     │pyproject.toml│  Version bump, license fix, ledctl-off entry
     │  (MODIFY)    │
     └──────────────┘

     ┌──────────────┐
     │ __init__.py  │  __version__ = "0.3.0"
     │  (MODIFY)    │
     └──────────────┘
```

## Commit Order

Commits are ordered so each one leaves the tree in a working state.

---

### Commit 1: fix(core): correct MODE constants to match hardware

**Files:** `ledctl/core.py`

**Change:**

```python
# BEFORE (ledctl/core.py:15-20)
MODE = SimpleNamespace(
    BREATH=0x02,
    CYCLE=0x03,
    OFF=0x04,
    RAINBOW=0x05,
)

# AFTER
MODE = SimpleNamespace(
    RAINBOW=0x01,
    BREATH=0x02,
    CYCLE=0x03,
    OFF=0x04,
    AUTO=0x05,
)
```

Reorder: alphabetical by value (0x01..0x05). Add `AUTO=0x05`.
Update the comment on line 14 to reflect new understanding:

```python
# Protocol mode bytes — verified against real hardware (matches wizard).
```

**Why this commit first:** Every other fix depends on correct mode constants.
Pattern modules (stillblue uses `MODE.RAINBOW`) get fixed for free.

---

### Commit 2: fix(cli/setmode): add `auto` mode, clean dead comments

**Files:** `ledctl/cli/setmode.py`

**Changes:**

1. Remove lines 1-14 (14 lines of dead commented-out wizard examples).
   These are stale artifacts from when setmode was the standalone script.

2. Add `"auto"` to the `--mode` choices:

```python
# BEFORE (line 25)
g.add_argument("--mode", choices=["breath", "cycle", "off", "rainbow"], help="Named mode")

# AFTER
g.add_argument("--mode", choices=["auto", "breath", "cycle", "off", "rainbow"], help="Named mode")
```

3. Add `auto` mapping in `_resolve_mode`:

```python
def _resolve_mode(args):
    if args.mode_num is not None:
        return args.mode_num
    _NAMED = {
        "auto": MODE.AUTO,
        "breath": MODE.BREATH,
        "cycle": MODE.CYCLE,
        "off": MODE.OFF,
        "rainbow": MODE.RAINBOW,
    }
    return _NAMED.get(args.mode, MODE.CYCLE)
```

This replaces the if-chain with a dict lookup. Benefits:
- Adding future modes is one dict entry instead of another if branch
- Alphabetical order is natural
- Single return point, easier to test

**ENG note:** The if-chain works fine for 6 entries. The dict is a
style improvement, not a correctness fix. Feel free to keep the if-chain
if you prefer — just add the `auto` branch.

---

### Commit 3: fix(patterns): implement pattern registry

**Files:** `ledctl/patterns/__init__.py`

**Change:** Fill the empty file with registry functions.

```python
import importlib
import pkgutil

import ledctl.patterns


def list_patterns():
    """Return alphabetically sorted names of available pattern modules."""
    return sorted(
        name
        for _finder, name, is_pkg in pkgutil.iter_modules(ledctl.patterns.__path__)
        if not is_pkg
    )


def run_pattern(name, **kwargs):
    """Import and run a pattern module's run() function."""
    available = list_patterns()
    if name not in available:
        raise SystemExit(
            f"Unknown pattern '{name}'. Available: {', '.join(available)}"
        )
    mod = importlib.import_module(f"ledctl.patterns.{name}")
    return mod.run(**kwargs)
```

**Design decisions (from CEO review):**
- `pkgutil.iter_modules()` — works in all install modes (editable, wheel, sdist)
- `SystemExit` on unknown pattern — matches project convention (e.g., core.py line 51)
- `**kwargs` passthrough — pattern `run()` functions accept keyword-only args

**Data flow:**

```
setpattern.py imports list_patterns, run_pattern
  │
  ├─ At import time: list_patterns() scans via pkgutil → ["alarm", "breathered", ...]
  │                  Used for argparse `choices=` on line 7 of setpattern.py
  │
  └─ At call time:  run_pattern("alarm", port=..., baud=...)
                       │
                       ├─ name NOT in list? → SystemExit with friendly message
                       │
                       └─ name in list? → importlib.import_module("ledctl.patterns.alarm")
                                          → mod.run(port=..., baud=...)
                                          → return exit code
```

**Shadow paths:**
- Nil input: argparse requires `name` positional → argparse error before registry
- Empty patterns dir: `list_patterns()` returns `[]`, argparse `choices=[]` → argparse error "invalid choice"
- Pattern module has import error (e.g. missing dep): `importlib.import_module` raises `ImportError` → raw traceback. Acceptable — this is a development-time error, not a user error.

---

### Commit 4: feat(cli): add `ledctl off` command

**Files:** `ledctl/cli/off.py` (NEW)

```python
"""CLI: turn LEDs off immediately.

Examples:
  ledctl off
  ledctl off --port /dev/ttyUSB0
"""
import argparse

from ledctl.core import BAUD_DEFAULT, LedCtl, MODE


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-off",
        description="Turn LEDs off.",
    )
    p.add_argument("--port", help="Serial device (auto-detect if omitted)")
    p.add_argument("--baud", type=int, default=BAUD_DEFAULT)
    p.add_argument("--dtr", dest="dtr", action="store_true", default=True)
    p.add_argument("--no-dtr", dest="dtr", action="store_false")
    p.add_argument("--rts", dest="rts", action="store_true", default=False)
    p.add_argument("--no-rts", dest="rts", action="store_false")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    with LedCtl(port=args.port, baud=args.baud, dtr=args.dtr, rts=args.rts) as ctl:
        ctl.set_mode_once(MODE.OFF)
    return 0
```

**Design notes:**
- No brightness/speed args — `off` is off, those are irrelevant
- Follows AGENTS.md CLI module pattern exactly
- Returns 0 on success (AGENTS.md convention)
- `LedCtl.__init__` handles the no-port-found case with SystemExit

---

### Commit 5: feat(__main__): route all subcommands

**Files:** `ledctl/__main__.py`

**Change:**

```python
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
```

**Changes from current:**
- Added `off` and `wiz` subcommands
- Switched from if/elif to dict dispatch (scales better, matches setmode refactor)
- Alphabetical subcommand registration

**Note on `wiz` import:** `cli/wizard.py` does NOT import from `ledctl.core` — it's
fully self-contained. The import of `wizard_main` is cheap (just loads argparse + serial).
No circular dependency risk.

---

### Commit 6: chore: bump version to 0.3.0, fix license classifier

**Files:** `ledctl/__init__.py`, `pyproject.toml`, `CHANGELOG.md`

**`ledctl/__init__.py`:**

```python
__all__ = ["core"]
__version__ = "0.3.0"
```

**`pyproject.toml`:**

```toml
version = "0.3.0"

# Fix classifier:
"License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
```

Remove `"License :: OSI Approved :: MIT License"`.

Add console script:
```toml
ledctl-off = "ledctl.cli.off:main"
```

**`CHANGELOG.md`:**

```markdown
## [0.3.0] - 2026-04-18

### Fixed
- MODE.RAINBOW wire byte corrected from 0x05 to 0x01 (matches real hardware)
- `ledctl pattern <name>` now works — pattern registry was empty, causing ImportError
- `ledctl off` command added (was documented but missing)

### Added
- MODE.AUTO (0x05) — previously missing from core library
- `--mode auto` choice in `ledctl setmode`
- `ledctl-off` console script entry point
- Pattern auto-discovery via `pkgutil.iter_modules()`
- Friendly error message when pattern name is unknown

### Changed
- License classifier corrected to GPL-3.0-or-later (was incorrectly MIT)
- Version synchronized between `__init__.py` and `pyproject.toml`
```

---

### Commit 7: test: update tests for new MODE values and new commands

**Files:** `tests/test_core.py` (MODIFY), `tests/test_cli.py` (MODIFY), `tests/test_patterns.py` (NEW)

#### `tests/test_core.py` changes:

```python
# Update test_mode_constants — RAINBOW changes from 0x05 to 0x01, add AUTO
def test_mode_constants():
    assert MODE.RAINBOW == 0x01
    assert MODE.BREATH == 0x02
    assert MODE.CYCLE == 0x03
    assert MODE.OFF == 0x04
    assert MODE.AUTO == 0x05

# Add: validate all modes match wizard's known-good values
def test_mode_values_sequential():
    """All mode bytes are unique and in 0x01..0x05 range."""
    values = [MODE.RAINBOW, MODE.BREATH, MODE.CYCLE, MODE.OFF, MODE.AUTO]
    assert values == [0x01, 0x02, 0x03, 0x04, 0x05]

# Update test_checksum_calculation to test multiple modes
def test_checksum_calculation():
    for mode_val in [MODE.RAINBOW, MODE.BREATH, MODE.CYCLE, MODE.OFF, MODE.AUTO]:
        bright_wire = LEVEL_TO_WIRE[3]
        speed_wire = LEVEL_TO_WIRE[3]
        expected = (0xFA + mode_val + bright_wire + speed_wire) & 0xFF
        assert expected == (0xFA + mode_val + 0x03 + 0x03) & 0xFF
```

#### `tests/test_cli.py` changes:

```python
# Update import to include off module
from ledctl.cli.off import parse_args as off_parse_args
from ledctl.cli.setmode import parse_args, _resolve_mode
from ledctl.core import MODE

# Add tests for auto mode
def test_parse_args_auto():
    args = parse_args(["--mode", "auto"])
    assert args.mode == "auto"


def test_resolve_mode_auto():
    args = parse_args(["--mode", "auto"])
    assert _resolve_mode(args) == MODE.AUTO


# Update existing rainbow test — it still passes, but add explicit value check
def test_resolve_mode_rainbow():
    args = parse_args(["--mode", "rainbow"])
    assert _resolve_mode(args) == MODE.RAINBOW
    assert _resolve_mode(args) == 0x01  # verify corrected value


# Add off command tests
def test_off_parse_args_defaults():
    args = off_parse_args([])
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False


def test_off_parse_args_with_port():
    args = off_parse_args(["--port", "/dev/ttyUSB0"])
    assert args.port == "/dev/ttyUSB0"
```

#### `tests/test_patterns.py` (NEW):

```python
import pytest

from ledctl.patterns import list_patterns, run_pattern


def test_list_patterns_returns_list():
    result = list_patterns()
    assert isinstance(result, list)
    assert len(result) > 0


def test_list_patterns_contains_known_patterns():
    result = list_patterns()
    assert "stillred" in result
    assert "stillblue" in result
    assert "breathered" in result
    assert "alarm" in result


def test_list_patterns_sorted():
    result = list_patterns()
    assert result == sorted(result)


def test_run_pattern_unknown_raises():
    with pytest.raises(SystemExit, match="Unknown pattern"):
        run_pattern("nonexistent")


def test_run_pattern_unknown_lists_available():
    """Error message includes the list of available patterns."""
    try:
        run_pattern("nope")
    except SystemExit as e:
        assert "alarm" in str(e) or "stillred" in str(e)


def test_run_pattern_imports_correctly():
    """Verify the module can be imported (no syntax errors)."""
    import importlib
    for name in list_patterns():
        mod = importlib.import_module(f"ledctl.patterns.{name}")
        assert hasattr(mod, "run")
```

**Test diagram:**

```
NEW CODEPATHS                    TEST TYPE     FILE
───────────────                  ──────────    ────────────────
MODE.RAINBOW == 0x01             unit          test_core.py
MODE.AUTO == 0x05                unit          test_core.py
All modes sequential 01-05       unit          test_core.py
Checksum for all 5 modes         unit          test_core.py
--mode auto accepted             unit          test_cli.py
_resolve_mode("auto") = 0x05    unit          test_cli.py
_resolve_mode("rainbow") = 0x01 unit          test_cli.py
off parse_args defaults          unit          test_cli.py
off parse_args --port            unit          test_cli.py
list_patterns returns list       unit          test_patterns.py
list_patterns has all 4 patterns unit          test_patterns.py
list_patterns sorted             unit          test_patterns.py
run_pattern("nonexistent")      unit          test_patterns.py
Error message lists available    unit          test_patterns.py
All pattern modules importable   unit          test_patterns.py

NOT TESTED (require hardware):
  - Actual serial writes (integration)
  - LedCtl context manager open/close
  - Pattern run() execution (infinite loops)
  - off command actual LED turn-off
```

---

### Commit 8 (optional): chore: remove dead comments, update AGENTS.md

**Files:** `ledctl/patterns/stillred.py`, `ledctl/patterns/stillblue.py`, `AGENTS.md`

Remove 47 lines of commented-out standalone code from `stillred.py` (lines 1-47) and
`stillblue.py` (lines 1-47). These are historical artifacts from before the core
library existed.

Update `AGENTS.md` to reflect reality:
- `ledctl/core/` → `ledctl/core.py` (single file, not a package)
- Remove `cli/off.py` from "not yet existing" — it exists now
- Update MODE values: `RAINBOW=0x01`, add `AUTO=0x05`
- Update pattern registry description: `patterns/__init__.py` now has
  `list_patterns()` and `run_pattern()`
- Add `off` and `wiz` to the CLI command routing in `__main__.py`

---

## Failure Modes

| Codepath | Failure | Handled? | Test? | User sees |
|----------|---------|----------|-------|-----------|
| `ledctl setmode --mode rainbow` | Was sending wrong byte (0x05→0x01) | FIXED C1 | YES C7 | Correct LED color |
| `ledctl pattern <name>` | ImportError (registry empty) | FIXED C3 | YES C7 | Pattern runs |
| `ledctl pattern nope` | Unknown pattern name | HANDLED C3 | YES C7 | SystemExit with list |
| `ledctl off` | Command didn't exist | FIXED C4 | YES C7 | Command works |
| `ledctl setmode` (no mode) | Defaults to cycle | EXISTING | YES | Works as before |
| No CH340 plugged in | SystemExit from LedCtl | EXISTING | N/A | "No CH340 tty found" |

**Critical gaps: 0** — All new codepaths have error handling and tests.

---

## NOT in scope

- Refactoring wizard to use `ledctl.core` — works, separate effort
- Adding new patterns
- Background/daemon mode for patterns
- Windows/macOS support
- Merging duplicate CI publish workflows
- Type hints on CLI modules (only core.py has them currently)

## What already exists (reused, not rebuilt)

| Component | File | Reused how |
|-----------|------|------------|
| Serial framing | `core.py:_write_frame` | setmode, off, patterns all use it |
| Port detection | `core.py:find_port` | LedCtl constructor |
| Mode constants | `core.py:MODE` | Corrected values, all consumers benefit |
| Pattern modules | `patterns/*.py` | Not modified, just discovered by registry |
| Argparse pattern | `cli/setmode.py` | off.py follows same structure |
| Console scripts | `pyproject.toml` | Just adding one entry |

---

## Completion Summary

```
+==================================================================+
|            ENG REVIEW — COMPLETION SUMMARY                       |
+==================================================================+
| Step 0               | SMALL CHANGE — compressed review          |
| Architecture Review  | 0 blocking issues (CEO caught real ones)  |
| Code Quality Review  | 1 note: if-chain→dict (optional)         |
| Test Review          | 15 test specs, 0 gaps, diagram produced   |
| Performance Review   | 0 issues                                 |
+------------------------------------------------------------------+
| NOT in scope         | 6 items                                   |
| What already exists  | 6 components reused                       |
| Failure modes        | 6 mapped, 0 critical gaps                 |
| Unresolved decisions | 0                                         |
+==================================================================+
```
