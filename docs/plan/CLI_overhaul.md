# CLI Overhaul — implementation plan

Status: **planned, not started** | Mode: MEDIUM-TIER CHANGE (CEO-reviewed)
Branch target: `main`

This document captures the finalized decisions for the CLI restructuring
described in TODO master items M1–M3, **after a CEO review pass** (see the
"CEO Review" section below). It is the authoritative reference for the
implementation; TODO.md tracks execution status and `CLI_overhaul_ENG.md`
holds the commit-by-commit engineering detail.

---

## Goals

1. Eliminate the two parallel protocol libraries (`wizard.py` re-declares
   `core.py` constants/transport). Single source of truth in `core.py`.
2. De-duplicate the serial-line option block shared by every subcommand.
3. Simplify the CLI command surface; drop wizard subcommands that duplicate
   or overlap top-level commands.
4. Standardize mode vocabulary on `breathing` (hard rename, no alias).

## Non-goals

- Adding new patterns or modes.
- New CLI features beyond consolidation (blink/pulse/scan are dropped, not
  relocated).
- Background/daemon mode, Windows/macOS support.
- Renaming the `ledctl` entry point or package.

---

## CEO Review

The first draft of this plan had several blocking issues found during a
verification pass against the actual codebase. They are recorded here so the
rationale is auditable.

### CR-F1 [BLOCKER] Two-level parsing architecture — serial flags live on
### subcommand parsers ONLY

The existing `__main__.py` does **not** use argparse subparser argument
delegation. It is a two-level scheme:

```python
args, rest = parser.parse_known_args()   # top-level grabs only `cmd`
dispatch[args.cmd](rest)                  # subcommand re-parses `rest`
```

The `sub.add_parser("off")` registrations are **vestigial** — they recognise
the command name and produce help text, but they carry no arguments. Each
subcommand's `main()` has its own independent `ArgumentParser` that re-parses
`rest`.

**Consequence (verified by test):** If the top-level parser is ALSO given the
serial flags via `parents=[serial_parser]`, then `parse_known_args()` consumes
`--baud`/`--port` at the top level and they do **not** appear in `rest`. The
subcommand's own parser re-parses `rest=[]` and falls back to its default —
**the user's flag value is silently lost**. This is a real, reproducible bug
class; the first draft of this plan would have introduced it.

**Verified behaviour matrix** (tested, Python 3.x argparse):

| invocation (top has serial flags) | cmd | rest | user value reaches subcommand? |
|-|-|-|-|
| `ledctl off --baud 12000` | `off` | `['--baud','12000']` | ✗ top.baud=10000, sub re-parses rest with default |
| `ledctl --baud 12000 off` | `off` | `[]` (consumed) | ✗ sub re-parses [] → default; value lost |
| `ledctl --baud 12000` (bare) | None | `[]` (consumed) | ✗ wizard re-parses [] → default; value lost |

| invocation (top has NO serial flags, subparsers have them via parent) | result |
|-|-|
| `ledctl off --baud 12000` | ✅ cmd=off, rest=`['--baud','12000']`, sub parses → 12000 |
| `ledctl wizard --baud 12000` | ✅ cmd=wizard, rest=`['--baud','12000']`, wizard parses → 12000 |
| `ledctl --baud 12000` (bare → wizard) | ✅ cmd=None, rest=`['--baud','12000']`, wizard parses → 12000 |

> NB: `ledctl --baud 12000 off` (flag **before** subcommand) raises
> `argument cmd: invalid choice: '12000'` because argparse doesn't know
> `--baud` takes a value when the top-level lacks it, so `12000` misbinds to
> the `cmd` positional. **This is an existing limitation of the two-level
> scheme** (the current wizard has the same shape, only its `-d`/`--dev` is on
> the top-level parser, which works precisely because it is registered there).
> Decision: serial flags are documented as **post-subcommand** only.
> `ledctl off --baud 12000` not `ledctl --baud 12000 off`. Acceptable UX; this
> is already the README pattern (`ledctl setmode breathing -p ...`).

**Design directive:** the shared serial parser is attached to each
**subcommand** parser (off / setmode / setpattern / wizard) via
`parents=[serial_parser]`. The top-level parser in `__main__.py` keeps **no**
serial flags; it only registers subcommand names + `dest="cmd"` exactly as
today. The first draft's instruction to add `parents=[...]` to the top-level
parser is **withdrawn** as a blocker.

### CR-F2 [BLOCKER] `docs/plan/` is gitignored — plan docs are not in VCS

`.gitignore:14` contains `*/plan/`, which matches `docs/plan/`. Verification:

```
$ git check-ignore -v docs/plan/TODO.md docs/plan/CLI_overhaul.md
.gitignore:14:*/plan/	docs/plan/TODO.md
.gitignore:14:*/plan/	docs/plan/CLI_overhaul.md
```

So `TODO.md`, `CLI_overhaul.md`, AND the pre-existing
`FIX-COMMANDS-IMPLEMENTATION.md` are all untracked. The repo currently has no
version-control trail for ANY planning doc.

**Directive:** the first commit of this overhaul MUST remove the `*/plan/` and
`*/plans/` lines from `.gitignore` so the plan docs can be committed at all.
Until that happens, every plan document is write-only-to-disk and invisible to
`git add`. This also retroactively recovers `FIX-COMMANDS-IMPLEMENTATION.md`
into VCS if desired.

### CR-F3 [HIGH] `--delay` is not reachable on the `setpattern` path

`off` and `setmode` construct `LedCtl` inside their own `main()`, so wiring
`LedCtl(ib_delay=args.delay)` there is trivial. **`setpattern` does not
construct `LedCtl` itself** — it calls `run_pattern(**kwargs)`, and each
pattern module constructs `LedCtl(port=port, baud=baud, dtr=dtr, rts=rts)`
internally with **no `ib_delay` argument**. None of
`alarm`/`breathered`/`stillred`/`stillblue` forward an `ib_delay`.

So "wire `--delay` into every subcommand `main()`" (first-draft M2.3) is
**insufficient for setpattern** — the value would be parsed and then dropped.

**Directive:** thread `ib_delay` explicitly: add `ib_delay` to each pattern's
`run()` signature (default `IB_DELAY_DEFAULT`), forward it to `LedCtl(...)`,
and have `setpattern.main()` pass `ib_delay=args.delay` into
`run_pattern(...)` → `mod.run(...)`. Default stays `IB_DELAY_DEFAULT`.

### CR-F4 [HIGH] Mode-name registry is duplicated in THREE places

The name↔value map for modes exists independently in:
- `setmode.py::_NAMED_MODES` (the dict used by `_resolve_mode`)
- `wizard.py::MODES` + `MODE_NAMES` (the dict + list the TUI indexes)
- `core.py::MODE` (the `SimpleNamespace` of constants — value-only, no names)

The first-draft plan treated the wizard↔core duplication but missed that
**setmode has its own third copy** (`_NAMED_MODES`). After the rename
`breath`→`breathing`, all three must stay in sync or the RAINBOW-bug class
returns by a new route.

**Directive:** make `core.py` the single source for the name registry too:

```python
MODE = SimpleNamespace(RAINBOW=0x01, BREATH=0x02, CYCLE=0x03, OFF=0x04, AUTO=0x05)
MODES = {"rainbow": MODE.RAINBOW, "breathing": MODE.BREATH,
         "cycle": MODE.CYCLE, "off": MODE.OFF, "auto": MODE.AUTO}
MODE_NAMES = list(MODES.keys())
```

`setmode.py` drops `_NAMED_MODES` and uses `core.MODES` directly (`choices=list
(MODES)` and `_resolve_mode` returns `MODES.get(args.mode, MODE.CYCLE)`).
`wizard.py` imports `MODES, MODE_NAMES` from core. This is folded into M1
(same consolidation theme) and tracked as M1.7.

### CR-F5 [MEDIUM] `-d` short-flag repurpose in the wizard

Wizard currently registers `-d`/`--dev` for the device (top-level).
`README.md` already advertises `-d`/`--delay SEC` as the inter-byte delay.
The shared parent parser wants `-d` for `--delay` to match the README
contract, and wizard's `--dev` becomes `--port` (unification). After the
change, `-d` on the wizard means **delay**, not **device** — a breaking
repurpose for any wizard user scripting `ledctl wiz -d /dev/ttyUSB0`.

**Directive:** accept the repurpose (it aligns the wizard with the README and
the rest of the CLI). Document in CHANGELOG. Keep `-d`/`--delay` (do NOT drop
the short form) because README already promises it; the wizard's old `-d` for
device is the outlier being removed.

### CR-F6 [MEDIUM] `setmode -b/-s` lack `choices=range(1,6)`

The wizard guards brightness/speed with `choices=range(1,6)` so argparse
rejects bad values with a friendly message. `setmode.py` has only
`type=int`, so `ledctl setmode --brightness 99` passes argparse and only
fails later inside `LedCtl._write_frame` with a bare `ValueError` ("brightness
/speed must be in 1..5"). UX inconsistency.

**Directive:** add `choices=range(1,6)` to setmode's `-b`/`-s` (M3, small
addition). `setpattern` keeps `default=None` (patterns set their own
defaults), so this applies to setmode only.

### CR-F7 [MEDIUM] Wizard TUI live port-switching with a held `LedCtl`

First-draft M1.3 said "hold one `LedCtl` for the TUI's lifetime and call
`set_mode_once`". The TUI's port switcher (`idx==0`, LEFT/RIGHT) lets the user
change port live. With a single long-lived `LedCtl` bound to one port, switching
requires closing+reopening. The first draft didn't address this.

**Directive:** two acceptable options (decide at ENG time, see ENG doc):
(a) `LedCtl` gains a `reopen(port=None)` or `port` setter that closes and
  re-opens, OR
(b) the TUI recreates a `LedCtl` whenever the port changes (cheap on a CH340).
Either is fine; option (b) is less new API surface. Document the chosen one.

### CR-F8 [LOW] `build/` and `*.egg-info/` are untracked, not committed

`git ls-files | grep -E '^(build|dist)/'` is **empty** — `build/` exists only
on disk (untracked, shows as `??`). `*.egg-info/` is already in `.gitignore`.
So "delete `build/`" is a local `rm -rf` with no git deletion commit needed;
the only git action is adding `build/` to `.gitignore`. First-draft C2 implied
a tracked deletion — corrected: no `git rm` needed.

### CR-F9 [LOW] `AGENTS.md` is gitignored

`.gitignore` lists `AGENTS.md`, and `FIX-COMMANDS-IMPLEMENTATION.md`
referenced "update AGENTS.md" as a step. There is no AGENTS.md in the repo
(glob confirms). It is a local-only convention file. No action required, but
the plan should stop referencing it as if it is tracked.

### CR-F10 [LOW] Device model naming drift

`pyproject.toml` description says "ACEMAGIC **P9/P9 Plus**" but `README.md`
says "ACEMAGIC **T9**". Two different model families for the same tool. Minor
brand consistency issue; defer to a docs pass (M5) — out of scope for the CLI
overhaul but logged.

### CR-F11 [LOW] README advertises `--background` / `--no-kill-existing`

README "Global pattern controls" lists these. No code implements them
anywhere. This is aspirational cruft that misleads users. Out of CLI-overhaul
scope; recommend removing from README in M5 rather than implementing.

### CR-F12 [DECISION] Version bump

The overhaul drops wizard subcommands and renames `breath`→`breathing` — both
behaviour-breaking. 0.3.0 is labelled Alpha with no compat guarantee, but a
minor bump signals the break. **Recommend bump to 0.4.0** and add a CHANGELOG
"### Changed"/"### Removed" block. **Open decision** — maintainer's call.

### CR-F13 [TEST] Wizard loses its only `main()` test

`tests/test_cli.py::test_wiz_main_accepts_argv` exercises `wiz_main(["list"])`.
`list` is being dropped (CR via M1.4), so this test must be deleted. New
coverage for the slimmed wizard: (a) `parse_args` defaults, (b) `main`
dispatches to `tui` (mock out `tui` so no curses/serial needed).

---

## Confirmed decisions (after CEO review)

| Decision | Choice | Rationale |
|-----------|--------|-----------|
| Serial-option mechanism | argparse parent parser, **attached to subcommand parsers only**, NOT the top-level | CR-F1: top-level would otherwise consume and lose the flags. |
| Serial-flag position | **Post-subcommand** only (`ledctl off --baud 12000`) | CR-F1: pre-subcommand misbinds to the `cmd` positional in the two-level scheme. |
| `--port` placement | With the other serial flags | Part of the line/transfer spec group. |
| Per-command opts | Standard flags (`-b`, `-s`, `--hz`, `--period`) | Consistent with argparse auto-help docs. |
| `--delay` semantics | Inter-byte delay, seconds between each byte written; LED micro UART drops back-to-back bytes. Default 5 ms; bump for flaky devices, lower for high-Hz patterns. | Lives in the shared parent parser. |
| `--delay` reach | Thread `ib_delay` through `run_pattern()` → pattern `run()` → `LedCtl` (CR-F3) | Otherwise setpattern path silently drops it. |
| Mode-name registry | Single source in `core.py`: `MODE` ns + `MODES` dict + `MODE_NAMES` list (CR-F4) | Eliminates the three-way duplication. |
| `find_ports()` plural | Add to `core.py`; `find_port()` becomes `find_ports()[0] or None` | Single source for one-port and multi-port enumeration. |
| Wizard subcommands | DROP all (`set`, `blink`, `pulse`, `list`, `scan`) | `set`=setmode; blink/pulse/scan have no home and are cut. |
| Mode name | Hard rename `breath`→`breathing` everywhere, no alias | Single vocabulary; wizard already uses `breathing`. |
| `-d` short flag | `-d` = `--delay` (per README); wizard's old `-d`/`--dev` removed (CR-F5) | Aligns wizard with README contract. |
| `setmode -b/-s` | Add `choices=range(1,6)` (CR-F6) | Consistent rejection UX with wizard. |
| Bare `ledctl` (no subcommand) | Routes to wizard | Preserves current behavior; document prominently. |
| Plan docs in VCS | Remove `*/plan/`, `*/plans/` from `.gitignore` first (CR-F2) | Else no plan doc can be committed. |
| Version | Bump to 0.4.0 (recommended; open decision, CR-F12) | Breaking changes. |

---

## Final command tree

```
ledctl wizard [SERIAL_FLAGS]            # alias: bare `ledctl` — TUI only
ledctl setmode  <mode> [SERIAL_FLAGS] [-b N] [-s N] [--hz HZ]
ledctl setpattern <pattern> [SERIAL_FLAGS] [-b N] [-s N] [--period SEC] [--mode-num BYTE]
ledctl off [SERIAL_FLAGS]
```

> SERIAL_FLAGS appear **after** the subcommand name (CR-F1). The `wizard`
> alias is the bare `ledctl` invocation; `ledctl wizard` is the explicit form.

### [SERIAL_FLAGS] (shared parent parser, on each subcommand)

```
--port PATH          Serial device (auto-detect if omitted)
--baud INT           default: BAUD_DEFAULT (10000)
--dtr / --no-dtr     assert/deassert DTR (default: assert)
--rts / --no-rts     assert/deassert RTS (default: deassert)
-d, --delay SEC      inter-byte delay, seconds (default 0.005)
    --ib-delay SEC   alias of --delay
```

### Per-command flags

- `setmode`:  `<mode> ∈ {rainbow, breathing, cycle, off, auto}` (or `--mode-num
  BYTE` in a mutually exclusive group with `--mode`), `-b 1..5`, `-s 1..5`,
  `--hz FLOAT`.
- `setpattern`: `<pattern>` (positional, `choices=list_patterns()`), `-b`,
  `-s`, `--period SEC`, `--mode-num BYTE`.
- `off`: none beyond serial flags.

> The `--mode`/`--mode-num` mutually-exclusive group on setmode is preserved.
> Only the `breath`→`breathing` choice string changes (CR-F4 unifies the
> registry).

---

## File-by-file change map (corrected)

### `ledctl/core.py`
- Add `find_ports() -> list[str]` (plural, deterministic glob-based,
  same order as the current `find_port`).
- Refactor `find_port() -> Optional[str]` to delegate:
  `return (find_ports() or [None])[0]`.
- Add the name registry (CR-F4):
  ```python
  MODES = {"rainbow": MODE.RAINBOW, "breathing": MODE.BREATH,
           "cycle": MODE.CYCLE, "off": MODE.OFF, "auto": MODE.AUTO}
  MODE_NAMES = list(MODES.keys())
  ```
- No other changes (constants already correct from 0.3.0).

### `ledctl/cli/common.py` (NEW)
- `make_serial_parser() -> argparse.ArgumentParser` — build with
  `add_help=False`.
- Imports `BAUD_DEFAULT`, `IB_DELAY_DEFAULT` from `ledctl.core`.
- Carries `--port`, `--baud` (default `BAUD_DEFAULT`),
  `--dtr/--no-dtr` (default True), `--rts/--no-rts` (default False),
  `-d/--delay` (default `IB_DELAY_DEFAULT`, alias `--ib-delay`).
- `--delay` help text must explain: seconds slept between each byte written;
  exists because the LED micro's UART drops back-to-back bytes; bump up for
  flaky devices, lower for high-refresh patterns.
- No `conflict_handler="resolve"` needed — subcommands do NOT re-declare any
  serial flag (they only inherit). (First draft's `conflict_handler` note is
  withdrawn: no conflict can arise.)

### `ledctl/cli/off.py`
- Replace inline `--port/--baud/--dtr/--no-dtr/--rts/--no-rts` block with
  `parents=[make_serial_parser()]`.
- Wire `LedCtl(port=args.port, baud=args.baud, ib_delay=args.delay, dtr=...,
  rts=...)`.
- No own flags.

### `ledctl/cli/setmode.py`
- Replace inline serial-arg block with `parents=[make_serial_parser()]`.
- Drop local `_NAMED_MODES`; import `MODES` from `core`. `_resolve_mode`
  becomes `return MODES.get(args.mode, MODE.CYCLE)` (with `--mode-num`
  override kept). `--mode` choices become `list(MODES)`.
- Change `--mode` choice/registry key `"breath"` → `"breathing"` (now just one
  edit point — in `core.MODES`).
- Add `choices=range(1,6)` to `-b`/`-s` (CR-F6).
- Wire `ib_delay=args.delay`.

### `ledctl/cli/setpattern.py`
- Replace inline serial-arg block with `parents=[make_serial_parser()]`.
- Wire `ib_delay=args.delay` into the `run_pattern(...)` call (CR-F3):
  add `ib_delay=args.delay` keyword.
- `--mode-num` stays as a per-pattern override (passed through to `run()`).

### `ledctl/patterns/__init__.py`
- `run_pattern(name, **kwargs)` already passes kwargs through; the new
  `ib_delay` kwarg flows automatically. No change needed here.

### `ledctl/patterns/{alarm,breathered,stillred,stillblue}.py`
- Add `ib_delay: float = IB_DELAY_DEFAULT` to each `run()` signature,
  forward it to `LedCtl(port=port, baud=baud, ib_delay=ib_delay, dtr=dtr,
  rts=rts)`.
- Replace `baud=10000` default with `baud=BAUD_DEFAULT` (import it).
- `stillblue.py:21`: delete the stale "Verify MODE.RAINBOW on your device"
  comment line.

### `ledctl/cli/wizard.py`
- DELETE: `BAUD`, `IB_DELAY`, `MODES`, `MODE_NAMES`, `LEVEL_TO_WIRE`,
  `find_ports()`, `checksum()`, `send_frame()`, the top-level `import serial`
  (becomes unused once `send_frame` is gone — ruff will flag it).
- DELETE: `set`/`blink`/`pulse`/`list`/`scan` subparser registration and their
  `main()` dispatch branches.
- IMPORT from `ledctl.core`: `BAUD_DEFAULT`, `IB_DELAY_DEFAULT`, `MODE`,
  `MODES`, `MODE_NAMES`, `LEVEL_TO_WIRE`, `find_ports`, `LedCtl`.
- Refactor `tui()`/`text_interactive()` to hold a `LedCtl` context and call
  `ctl.set_mode_once(mode, b, s)`. Handle live port switching per CR-F7
  (recommend: recreate `LedCtl` when the port changes in the Port field).
- `parse_args()` only carries the shared serial flags (via parent parser),
  `--dev`/`-d`-for-device removed. No subparsers.
- `main()` calls `tui(args.port, args.dtr, args.rts, args.delay)` directly.
  If `args.port` is None, default inside `tui()` (do not eagerly pick
  `find_ports()[0]` — the TUI port switcher should be able to refresh).

### `ledctl/__main__.py`
- **NO serial flags on the top-level parser** (CR-F1). Keep it minimal:
  `prog="ledctl"`, `add_subparsers(dest="cmd")`, register the four subcommand
  names (off/setmode/setpattern/wizard) with help text only, `required=False`
  (so bare `ledctl` is allowed), dict dispatch, bare→wizard as today.
- Help text for `setpattern`: generic ("run a predefined pattern") — do NOT
  hardcode `stillred/stillblue/...` examples since the registry is
  auto-discovered.
- `-d` does **not** live here (it is a serial flag on subcommands per CR-F5).

### `tests/`
- `test_core.py`: add `test_find_ports_returns_list` (returns list of str or
  empty); add `test_mode_names_registry` (`core.MODES["breathing"] == MODE.BREATH`,
  `core.MODE_NAMES` is sorted-sensible).
- `test_cli.py`: rename `--mode breath` cases to `--mode breathing`.
- `test_cli.py`: add parent-parser coverage — `off`/`setmode`/`setpattern`/
  `wizard` each expose `--delay` and the expected serial-flag defaults.
- `test_cli.py`: drop `test_wiz_scan_parse_args`, `test_wiz_set_parse_args`,
  `test_wiz_main_accepts_argv` (subcommands gone, CR-F13). Add:
  `test_wiz_parse_args_defaults`, `test_wiz_main_calls_tui` (monkeypatch `tui`).
- `tests/conftest.py` (NEW or extend): tripwire — `core.MODE.RAINBOW == 0x01`
  and `core.MODES["rainbow"] == core.MODE.RAINBOW` (guards the registry
  introduced by CR-F4 against silent drift).

---

## Commit order (proposed, corrected)

Commits leave the tree working and tests green after each step.

### C1. chore(infra): un-ignore docs/plan, remove build/ artifact, add plan docs
- Remove `*/plan/` and `*/plans/` lines from `.gitignore` (CR-F2). Add `build/`
  to `.gitignore`.
- `rm -rf build/` (local-only, untracked — no `git rm`).
- `git add docs/plan/TODO.md docs/plan/CLI_overhaul.md
  docs/plan/CLI_overhaul_ENG.md docs/plan/FIX-COMMANDS-IMPLEMENTATION.md`
  (recover the previously-ignored plan docs into VCS).
- Remove "Verify MODE.RAINBOW" comment from `stillblue.py:21` (M4.1).
- Pure chore; no code behaviour change.

### C2. refactor(core): add find_ports() plural + MODES/MODE_NAMES registry
- Files: `ledctl/core.py`.
- Add `find_ports()`, refactor `find_port()` to delegate.
- Add `MODES` dict + `MODE_NAMES` list (CR-F4).
- Tests: extend `test_core.py` with `find_ports()` and registry tests.
- Tree stays working — no consumer changed yet (setmode/wizard still use their
  own copies; those go away in C5/C6).

### C3. refactor(cli/common): introduce shared serial parent parser
- NEW `ledctl/cli/common.py`.
- No subcommand wired to it yet — pure addition, tests green.

### C4. refactor(cli): wire subcommands to parent parser; thread ib_delay (CR-F3)
- Files: `off.py`, `setmode.py`, `setpattern.py`, `patterns/*.py`.
- Replace inline serial args with `parents=[make_serial_parser()]`.
- Wire `ib_delay=args.delay` into `off`/`setmode` (direct) and `setpattern`
  (via `run_pattern`→`run()`). Add `ib_delay` to each pattern `run()` signature
  and forward to `LedCtl`.
- Replace `default=10000` literals with `BAUD_DEFAULT` imports in
  `patterns/*.py` and any remaining CLI module.
- Add `choices=range(1,6)` to setmode `-b`/`-s` (CR-F6).
- Update `test_cli.py` to assert `args.delay` default and `--delay` parsing on
  off/setmode/setpattern.
- Tests green; ruff clean.

### C5. refactor(wizard): import from core; make TUI-only
- DELETE duplicate constants/transport; import from `core` (`MODE`, `MODES`,
  `MODE_NAMES`, `LEVEL_TO_WIRE`, `find_ports`, `LedCtl`, defaults).
- DROP `set`/`blink`/`pulse`/`list`/`scan` subcommands + dispatch.
- Refactor TUI to hold a `LedCtl` context; recreate it on port change (CR-F7).
- Simplify `parse_args()` (parent parser, no subparsers, no `-d`/`--dev`) and
  `main()` (calls `tui` directly).
- **`__main__.py` stays minimal — NO serial flags added to top-level** (CR-F1).
- Drop now-obsolete wizard tests; add `test_wiz_parse_args_defaults` and
  `test_wiz_main_calls_tui` (mock `tui`).
- Tests green; ruff clean.

### C6. refactor(setmode): consume core.MODES; hard-rename breath → breathing
- `setmode.py`: drop `_NAMED_MODES`, use `core.MODES`; `--mode` choices =
  `list(MODES)`.
- `test_cli.py`: rename `breath` cases to `breathing`; assert
  `MODES["breathing"] == MODE.BREATH`.
- No backward-compat alias.

### C7. chore(docs): document bare-ledctl default & help epilog; CHANGELOG
- README "Quick start": note bare `ledctl` launches the curses TUI; serial
  flags go after the subcommand.
- `__main__.py` top-level epilog showing the four forms.
- CHANGELOG entry for breaking changes: wizard subcommand removal,
  `breath`→`breathing`, wizard `-d` repurpose (device→delay), `--delay` now
  honored on all paths, `MODES` registry centralised.
- Optional (defer to M5): fix broken README doc links.

### C8 (optional). chore(version): bump to 0.4.0
- `ledctl/__init__.py` + `pyproject.toml` version → `0.4.0` (CR-F12, open).
- CHANGELOG `## [0.4.0]` block (if not already added in C7).

---

## Verification gates (per commit)

After each commit:
1. `python -m pytest -q` — all green.
2. `python -m ruff check ledctl tests` — clean.
3. Smoke import: `python -c "import ledctl.__main__; import ledctl.cli.wizard"`.

After C4 and C5 additionally:
4. `ledctl off --help`, `ledctl setmode --help`, `ledctl setpattern --help`,
   `ledctl wizard --help` each show the serial flags exactly once and own
   flags only — no duplication.
5. `ledctl --help` does NOT show `--baud`/`--port`/etc at the top level
   (CR-F1 enforced).
6. `git ls-files | grep -E '^(build|dist)/'` is empty (since C1).
7. `git check-ignore docs/plan/TODO.md` returns non-zero (file is tracked).

---

## Risk matrix (corrected)

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Top-level parser consumes serial flags and subcommand never sees them | **was high in first draft; eliminated** | CR-F1 directive: serial flags on subcommand parsers ONLY. Verified by test matrix. |
| `--delay` silently dropped on setpattern path | was high | CR-F3: thread `ib_delay` through `run_pattern`→`run`→`LedCtl`. |
| Three-way mode-name registry drift | was high | CR-F4: single `MODES` dict in core; conftest tripwire. |
| Wizard TUI regression after `LedCtl` context refactor | medium | CR-F7: recreate context on port change; C5 mocks `tui` in `test_wiz_main_calls_tui`. |
| Removed wizard subcommands break a user's script | low-medium | Never in README quickstart; `set`=setmode. Note in CHANGELOG (C7). |
| `breathing` rename breaks `--mode breath` scripts | low-medium | No alias; CHANGELOG note. Alpha, no compat guarantee. |
| `-d` repurpose breaks wizard `-d /dev/x` users | low-medium | CHANGELOG note (C7); -d now matches README's documented meaning. |
| `ledctl --baud 12000 off` (flag before sub) errors | low (existing limitation) | Documented as post-subcommand-only UX; matches README's existing examples. |
| Plan docs can't be committed | was blocker | CR-F2: un-ignore `docs/plan/` in C1 before any plan-doc commit. |

---

## Out of scope (owned by other TODO items)

- Documentation link fixes (M5).
- Additional test coverage for `wizard.main` new path beyond the minimal C5 set
  (M6).
- Moving `--mode-num` onto `setpattern` as a first-class mutex (later change).
- README `--background`/`--no-kill-existing` removal (M5, CR-F11).
- Device-model naming drift P9 vs T9 (CR-F10, M5).

## Open decisions

1. **Version bump to 0.4.0?** (CR-F12) — recommended; maintainer's call.
2. **Wizard port-switch mechanism** (CR-F7): `LedCtl.reopen()` vs recreate —
   ENG doc picks recreate (less API surface); confirm.