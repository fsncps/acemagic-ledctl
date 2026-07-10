# TODO — cleanup & consolidation

Follows the architecture review. Master items are independent work units;
sub-items are ordered steps within each. Resolve in order M4 → M1 → M2 → M3
(M4 is trivial cleanup, M1 unblocks M2/M3).

---

## M1. Consolidate protocol into `core.py`; slim `wizard.py` to TUI-only

The wizard currently re-declares the entire protocol (BAUD, IB_DELAY, MODES,
LEVEL_TO_WIRE, find_ports, send_frame). This is the single biggest source of
redundancy and the exact class of bug that bit MODE.RAINBOW.

- [ ] M1.1 Delete duplicated constants from `wizard.py`: `BAUD`, `IB_DELAY`,
      `MODES`, `MODE_NAMES`, `LEVEL_TO_WIRE`. Import from `core.py` instead
      (`BAUD_DEFAULT`, `IB_DELAY_DEFAULT`, `MODE`, `LEVEL_TO_WIRE`).
- [ ] M1.2 Add `find_ports()` (plural, deterministic glob-based) to `core.py`.
      Refactor `find_port()` to `find_ports()[0] or None`. Replace
      `wizard.find_ports()` with `core.find_ports()`.
- [ ] M1.3 Replace `wizard.send_frame()` with `LedCtl.set_mode_once()`.
      Wizard currently opens/closes a new `serial.Serial` per frame; refactor
      to hold one `LedCtl` context for the TUI's lifetime.
- [ ] M1.4 Drop ALL wizard subcommands (`set`, `blink`, `pulse`, `list`,
      `scan`). Wizard becomes TUI-only — no subcommands, no args. `set` is
      covered by `ledctl setmode`; `blink`/`pulse`/`scan` are dropped entirely.
- [ ] M1.5 Simplify `wizard.parse_args()` to only the top-level serial flags
      (now coming from the shared parent parser, M2) plus nothing else. Remove
      the `set`/`blink`/`pulse`/`scan`/`list` subparser registration and their
      `main()` dispatch branches.
- [ ] M1.6 Add a `tests/conftest.py` tripwire: assert the wizard's imported
      constants equal core's (e.g. `wizard.MODES["rainbow"] == MODE.RAINBOW`)
      once M1.1 lands — guards against reintroducing the duplicate source.

## M2. Unify serial options via shared parent parser

`[--baud] [--dtr] [--no-dtr] [--rts] [--no-rts]` is duplicated verbatim in
`off.py`, `setmode.py`, `setpattern.py`, `wizard.py`; `--port`/`--delay`
inconsistently present.

- [ ] M2.1 Create `ledctl/cli/common.py` with `make_serial_parser()` returning
      an `argparse.ArgumentParser(add_help=False)` carrying: `--port`,
      `--baud` (default `BAUD_DEFAULT`), `--dtr/--no-dtr` (default True),
      `--rts/--no-rts` (default False), `--delay`/`-d` (default
      `IB_DELAY_DEFAULT`, alias `--ib-delay`). Help text must explain the
      inter-byte delay: seconds slept between each byte written; needed because
      the LED micro's UART drops bytes that arrive back-to-back; bump up for
      flaky devices, down for high-refresh patterns.
- [ ] M2.2 Replace inline serial-arg blocks in `off.py`, `setmode.py`,
      `setpattern.py`, `wizard.py` with `parents=[serial_parser]`.
- [ ] M2.3 Wire `--delay` into `LedCtl(ib_delay=args.delay)` in every
      subcommand `main()` — currently only the wizard honored it.
- [ ] M2.4 Import `BAUD_DEFAULT` everywhere instead of hardcoding `10000`
      (currently `setmode.py:21`, `setpattern.py:9`, all pattern `run()`s).

## M3. Review & restructure the CLI command surface

- [ ] M3.1 Confirm final command tree:
        - `ledctl wizard` (alias: bare `ledctl`) — TUI only, no subcommands.
        - `ledctl setmode <mode> [-b] [-s] [--hz]` — single frame or repeat.
        - `ledctl setpattern <pattern> [-b] [-s] [--period] [--mode-num]`.
        - `ledctl off` — no own flags (gets serial flags from the parent parser
          only).
- [ ] M3.2 `__main__.py`: register subparsers with the shared parent parser;
      per-subcommand parsers add only their own opts. Bare `ledctl` (no
      subcommand) routes to wizard.
- [ ] M3.3 Document the bare-`ledctl`→wizard default prominently (README +
      top-level `--help` epilog) — it launches an interactive curses TUI and
      can hang a scripted no-arg invocation.
- [ ] M3.4 Hard-rename mode vocab `breath` → `breathing` everywhere:
      `setmode.py` choices, `_NAMED_MODES`, tests. No backward-compat alias.
      Also align with `wizard.py` (already uses `breathing`).

## M4. Remove stale comments & artifacts
- [ ] M4.1 Delete the "Verify MODE.RAINBOW on your device" note in
      `stillblue.py:21` (RAINBOW verified at 0x01).
- [ ] M4.2 Delete `build/` directory.
- [ ] M4.3 Add `build/`, `*.egg-info/`, `dist/` to `.gitignore`.
- [ ] M4.4 Confirm `ledctl/` is the sole tracked source root: `git ls-files |
      grep -E '^(build|dist)/'` should be empty after M4.2.

## M5. Documentation hygiene (low priority)
- [ ] M5.1 Fix broken README links: `docs/release-process.md`,
      `docs/license-choice.md`, `ROADMAP.md`, `CONTRIBUTING.md` — stub them or
      remove the links.
- [ ] M5.2 Fix stale internal reference in
      `docs/plan/FIX-COMMANDS-IMPLEMENTATION.md` (points at non-existent
      `docs/plans/2026-04-18-fix-commands.md`).

## M6. Tests (low priority)
- [ ] M6.1 Revisit after M1/M2/M3 land — add coverage for the shared parent
      parser and the slimmed wizard.
- [ ] M6.2 (optional) Unit-test `wizard.main` `set`/`blink`/`pulse`/`scan`
      parse_args paths — N/A once M1.4 drops them; instead cover the new TUI
      entry path.