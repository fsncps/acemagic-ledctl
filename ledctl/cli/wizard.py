# ledctl/cli/wizard.py
"""
LED wizard (curses, centered, sticky):
  ↑/↓   move between fields
  ←/→   change value
  Enter apply current selection (built-ins = one-shot, patterns = background)
  o     Off (one-shot)  — also kills any running pattern
  q     Quit            — re-issues current selection so it "sticks"

Notes:
- Built-ins: single frame via core.send_frame_one_shot()
- Patterns: background process via `python -m ledctl setpattern <pattern> ...` (detached)
- Changing selection or applying clears any existing setpattern loops
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from typing import List, Tuple

from ledctl.core import (
    BAUD_DEFAULT,
    IB_DELAY_DEFAULT,
    BUILTIN_MODES,
    find_ports,
    send_frame_one_shot,
)
from ledctl.patterns import list_patterns

# Built-ins from core
BUILTINS = set(BUILTIN_MODES.keys())

# Pattern arg rules
PATTERN_ONLY_B = {"stillred", "stillblue"}  # brightness only
PATTERN_ONLY_NONE = {"alarm"}  # no args
PATTERN_SPEED_PRESETS = {"breathered"}  # speed presets 1..4

# -------------------- Human-facing info text --------------------

MODE_INFO = {
    "off": (
        "Turn LEDs off immediately.\n"
        "This sends a single frame to the controller; nothing keeps running afterward."
    ),
    "cycle": (
        "Built-in device color cycle.\n"
        "• Brightness (1..5): 1=dim ↔ 5=bright\n"
        "• Speed (1..5): 1=fast ↔ 5=slow\n"
        "Useful as a baseline test that the controller responds to frames."
    ),
    "breathing": (
        "Built-in breathing effect using the device palette.\n"
        "Controls behave like CYCLE (brightness & speed). Timing is handled by the firmware."
    ),
    "rainbow": (
        "Built-in rainbow effect (multi-hue rotation).\n"
        "Brightness and speed map as usual. If you see stepping, try lower speed."
    ),
}

PATTERN_INFO = {
    "stillred": (
        "Solid red produced by repeatedly resetting the device CYCLE mode at high rate.\n"
        "• Args: -b/--brightness only (1..5). Speed is ignored.\n"
        "This is a host-driven loop (detached in background)."
    ),
    "stillblue": (
        "Solid blue produced by repeatedly resetting the device RAINBOW mode at high rate.\n"
        "• Args: -b/--brightness only (1..5). Speed is ignored.\n"
        "Host-driven loop (detached)."
    ),
    "breathered": (
        "Red-only breathing with measured preset pairs (speed → brightness,period).\n"
        "Use -s 1..4:\n"
        "  s=1 → b=4, ~5000 ms per cycle\n"
        "  s=2 → b=3, ~4000 ms per cycle\n"
        "  s=3 → b=2, ~3000 ms per cycle\n"
        "  s=4 → b=1, ~1800 ms per cycle\n"
        "Brightness from the UI is ignored; speed selects the preset."
    ),
    "alarm": (
        "Aggressive blink meant to draw attention.\n"
        "No adjustable arguments. Runs as a background loop until replaced or killed."
    ),
}

GENERAL_INFO = (
    "About the port (/dev/ttyUSB0): typically a CH340 USB↔TTL bridge connected to the LED MCU.\n"
    "DTR/RTS: modem-control lines exposed by the USB bridge. Some devices gate power/logic based\n"
    "on these signals. If you observe inconsistent behavior, try toggling DTR/RTS and re-apply."
)

# -------------------- enablement helpers --------------------


def brightness_enabled(name: str) -> bool:
    if name in BUILTINS:
        return True
    if name in PATTERN_ONLY_B:
        return True
    if name in PATTERN_SPEED_PRESETS:
        return False
    if name in PATTERN_ONLY_NONE:
        return False
    return True


def speed_enabled(name: str) -> bool:
    if name in BUILTINS:
        return True
    if name in PATTERN_ONLY_B:
        return False
    if name in PATTERN_SPEED_PRESETS:
        return True
    if name in PATTERN_ONLY_NONE:
        return False
    return True


# -------------------- pattern process helpers --------------------


def _pattern_pids() -> List[int]:
    """Find running 'ledctl setpattern' processes (excluding self)."""
    me = os.getpid()
    pids: List[int] = []
    try:
        out = subprocess.check_output(["pgrep", "-f", r"ledctl.*setpattern"], text=True)
        for s in out.splitlines():
            if s.strip().isdigit():
                pid = int(s.strip())
                if pid != me:
                    pids.append(pid)
        return pids
    except Exception:
        pass
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
        for line in out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            pid_s, cmd = parts
            if not pid_s.isdigit():
                continue
            pid = int(pid_s)
            if pid == me:
                continue
            if "ledctl" in cmd and " setpattern " in cmd and "grep" not in cmd:
                pids.append(pid)
    except Exception:
        pass
    return pids


def _pattern_is_running(pattern: str) -> bool:
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
        needle = f" setpattern {pattern} "
        return any(needle in f" {line} " for line in out.splitlines())
    except Exception:
        return False


def _kill_running_patterns() -> int:
    """SIGTERM then SIGKILL any setpattern processes. Return count found."""
    pids = _pattern_pids()
    if not pids:
        return 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    try:
        import time

        time.sleep(0.5)
    except Exception:
        pass
    survivors = set(_pattern_pids())
    for pid in survivors:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    return len(pids)


def _spawn_pattern_background(
    *,
    pattern: str,
    port: str | None,
    baud: int,
    dtr: bool,
    rts: bool,
    brightness: int | None = None,
    speed: int | None = None,
) -> int | None:
    """Detach a new `ledctl setpattern <pattern> ...` (like '&')."""
    cmd = [sys.executable, "-m", "ledctl", "setpattern", pattern]
    if port:
        cmd += ["--port", port]
    cmd += ["--baud", str(baud)]
    cmd += ["--dtr"] if dtr else ["--no-dtr"]
    cmd += ["--rts"] if rts else ["--no-rts"]
    if (pattern in PATTERN_ONLY_B) and (brightness is not None):
        cmd += ["-b", str(brightness)]
    if (pattern in PATTERN_SPEED_PRESETS) and (speed is not None):
        cmd += ["-s", str(max(1, min(4, int(speed))))]

    with open(os.devnull, "wb") as devnull:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=devnull,
                stderr=devnull,
                stdin=devnull,
                preexec_fn=os.setsid,  # detach (nohup-like)
                close_fds=True,
                env=dict(os.environ, PYTHONUNBUFFERED="1"),
            )
            return proc.pid
        except Exception:
            return None


# -------------------- centered curses UI --------------------


def _wrap(text: str, width: int) -> list[str]:
    """Simple word-wrap to a list of lines that fit `width`."""
    import textwrap

    wrapped: list[str] = []
    for para in text.splitlines():
        if not para.strip():
            wrapped.append("")
            continue
        wrapped.extend(
            textwrap.wrap(
                para, width=width, break_long_words=False, replace_whitespace=False
            )
        )
    return wrapped


def _center_box(
    stdscr, lines: list[str], title: str = "", highlight_rows: set[int] | None = None
):
    """Create a centered window sized to `lines` and render them (bold highlights)."""
    import curses

    H, W = stdscr.getmaxyx()

    # Before drawing a differently-sized window, clear the background so old boxes don't linger.
    stdscr.erase()
    stdscr.refresh()

    inner_width = max(60, *(len(ln) for ln in lines)) if lines else 60
    inner_height = len(lines) + 4  # border + padding
    w = min(W - 2, inner_width + 4)
    h = min(H - 2, inner_height)
    y0 = max(0, (H - h) // 2)
    x0 = max(0, (W - w) // 2)
    win = curses.newwin(h, w, y0, x0)
    win.box()
    if title:
        try:
            win.addstr(0, 2, f" {title} ", curses.A_BOLD)
        except Exception:
            pass

    # Render lines with optional bold for highlighted rows
    highlight_rows = highlight_rows or set()
    y = 2
    for i, ln in enumerate(lines):
        txt = ln[: max(0, w - 4)]
        attr = curses.A_BOLD if i in highlight_rows else 0
        try:
            win.addstr(y, 2, txt, attr)
        except Exception:
            pass
        y += 1
        if y >= h - 1:
            break
    win.refresh()


def _compose_lines(
    port: str, cur: str, b: int, s: int, dtr: bool, rts: bool, max_width: int
) -> list[str]:
    """Build wrapped lines for the centered panel."""
    header = "↑/↓ Field   ←/→ Change   Enter=Apply   o=Off   q=Quit (sticks)"
    fields = [
        f"Port:       {port}",
        f"Name:       {cur}",
        f"Brightness: {b}  (1..5){'' if brightness_enabled(cur) else '  [disabled]'}",
        f"Speed:      {s}  (1..5){'' if speed_enabled(cur) else '  [disabled]'}",
        f"DTR:        {'ON' if dtr else 'OFF'}",
        f"RTS:        {'ON' if rts else 'OFF'}",
    ]

    info_block = []
    if cur in BUILTINS:
        info_block += _wrap(MODE_INFO.get(cur, ""), max_width)
    else:
        info_block += _wrap(PATTERN_INFO.get(cur, ""), max_width)

    info_block += [""]
    info_block += _wrap(GENERAL_INFO, max_width)

    lines = [header, ""] + fields + [""] + info_block
    return lines


def _curses_ui(
    port_hint: str | None, dtr: bool, rts: bool, delay: float
) -> Tuple[str, int, int, bool, bool, str, bool]:
    """Run the TUI and return the final selection + whether a pattern is running.
    Returns: (name, bright, speed, dtr, rts, port, pattern_running_now)
    """
    import curses

    ports = find_ports()
    if not ports:
        print("No CH340 tty found.")
        return ("off", 3, 3, dtr, rts, port_hint or "", False)

    port_idx = 0
    if port_hint and port_hint in ports:
        port_idx = ports.index(port_hint)

    names = sorted(BUILTINS | set(list_patterns()))
    if "off" in names:
        names.remove("off")
        names.insert(0, "off")

    name_idx = 0
    bright = 3
    speed = 3
    _dtr, _rts = dtr, rts
    idx = 1  # field cursor: 0..5  (Port, Name, Brightness, Speed, DTR, RTS)
    pattern_running = False

    def draw(stdscr):
        H, W = stdscr.getmaxyx()
        # Compose lines with wrapping margin that fits the centered window nicely
        wrap_w = max(60, min(W - 10, 100))
        cur = names[name_idx]
        lines = _compose_lines(ports[port_idx], cur, bright, speed, _dtr, _rts, wrap_w)

        # Highlight the currently selected field row: header + blank + fields offset
        field_base = 2  # header (0), blank (1), then fields start at line index 2
        highlight_map = {
            0: field_base + 0,  # Port
            1: field_base + 1,  # Name
            2: field_base + 2,  # Brightness
            3: field_base + 3,  # Speed
            4: field_base + 4,  # DTR
            5: field_base + 5,  # RTS
        }
        hi = {highlight_map[idx]}
        _center_box(stdscr, lines, title="LEDCTL Wizard", highlight_rows=hi)

    def apply_current():
        nonlocal pattern_running
        _kill_running_patterns()
        cur = names[name_idx]
        port = ports[port_idx]
        if cur in BUILTINS:
            send_frame_one_shot(
                port=port,
                mode=BUILTIN_MODES[cur],
                brightness=bright,
                speed=speed,
                baud=BAUD_DEFAULT,
                dtr=_dtr,
                rts=_rts,
                ib_delay=delay,
            )
            pattern_running = False
        else:
            _spawn_pattern_background(
                pattern=cur,
                port=port,
                baud=BAUD_DEFAULT,
                dtr=_dtr,
                rts=_rts,
                brightness=bright if cur in PATTERN_ONLY_B else None,
                speed=speed if cur in PATTERN_SPEED_PRESETS else None,
            )
            pattern_running = True

    def main(stdscr):
        nonlocal idx, port_idx, name_idx, bright, speed, _dtr, _rts, pattern_running
        curses.curs_set(0)
        draw(stdscr)
        while True:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                cur = names[name_idx]
                return (
                    cur,
                    bright,
                    speed,
                    _dtr,
                    _rts,
                    ports[port_idx],
                    pattern_running,
                )
            if key in (ord("o"), ord("O")):
                _kill_running_patterns()
                send_frame_one_shot(
                    port=ports[port_idx],
                    mode=BUILTIN_MODES.get("off", list(BUILTIN_MODES.values())[0]),
                    brightness=bright,
                    speed=speed,
                    baud=BAUD_DEFAULT,
                    dtr=_dtr,
                    rts=_rts,
                    ib_delay=delay,
                )
                pattern_running = False
                draw(stdscr)
                continue

            if key == curses.KEY_UP:
                idx = (idx - 1) % 6
            elif key == curses.KEY_DOWN:
                idx = (idx + 1) % 6
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                step = -1 if key == curses.KEY_LEFT else 1
                cur = names[name_idx]
                if idx == 0:
                    ports[:] = find_ports() or ports
                    if ports:
                        port_idx = (port_idx + step) % len(ports)
                elif idx == 1:
                    name_idx = (name_idx + step) % len(names)
                    _kill_running_patterns()
                    pattern_running = False
                elif idx == 2 and brightness_enabled(cur):
                    bright = min(5, max(1, bright + step))
                elif idx == 3 and speed_enabled(cur):
                    speed = min(5, max(1, speed + step))
                elif idx == 4:
                    _dtr = not _dtr
                elif idx == 5:
                    _rts = not _rts
            elif key in (curses.KEY_ENTER, 10, 13):
                apply_current()
            draw(stdscr)

    import curses

    return curses.wrapper(main)


# -------------------- CLI shell --------------------


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl wiz",
        description=(
            "Interactive wizard (curses). Built-ins apply instantly; patterns run in background.\n"
            "On quit, the current selection is re-issued so it sticks."
        ),
    )
    p.add_argument("-d", "--dev", default=None, help="serial device (auto-detect)")
    p.add_argument(
        "--dtr",
        dest="dtr",
        action="store_true",
        default=True,
        help="assert DTR (default)",
    )
    p.add_argument("--no-dtr", dest="dtr", action="store_false", help="deassert DTR")
    p.add_argument(
        "--rts", dest="rts", action="store_true", default=False, help="assert RTS"
    )
    p.add_argument("--no-rts", dest="rts", action="store_false", help="deassert RTS")
    p.add_argument(
        "--delay", type=float, default=IB_DELAY_DEFAULT, help="inter-byte delay (sec)"
    )
    return p.parse_args(argv)


def _reissue_after_quit(
    name: str, b: int, s: int, dtr: bool, rts: bool, port: str, pattern_running: bool
):
    """After curses exits, re-issue selection so it persists."""
    if name in BUILTINS:
        cmd = [
            sys.executable,
            "-m",
            "ledctl",
            "setmode",
            name,
            "-b",
            str(b),
            "-s",
            str(s),
        ]
        if port:
            cmd += ["--port", port]
        cmd += ["--dtr" if dtr else "--no-dtr", "--rts" if rts else "--no-rts"]
        cmd += ["--baud", str(BAUD_DEFAULT)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        if not _pattern_is_running(name):
            _spawn_pattern_background(
                pattern=name,
                port=port if port else None,
                baud=BAUD_DEFAULT,
                dtr=dtr,
                rts=rts,
                brightness=b if name in PATTERN_ONLY_B else None,
                speed=s if name in PATTERN_SPEED_PRESETS else None,
            )


def main(argv=None):
    a = parse_args(argv)
    ports = find_ports()
    dev = a.dev or (ports[0] if ports else None)
    if not dev:
        print("No CH340 tty found.")
        return 1

    name, b, s, dtr, rts, port, pat_running = _curses_ui(
        port_hint=dev, dtr=a.dtr, rts=a.rts, delay=a.delay
    )
    _reissue_after_quit(name, b, s, dtr, rts, port, pat_running)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
