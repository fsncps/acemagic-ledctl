# ledctl/cli/wizard.py
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

# ---- pretty output (Rich) ----
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.box import ROUNDED

    RICH = True
    console = Console()
except Exception:
    RICH = False
    console = None

# ---- optional compact selectors ----
try:
    import questionary as q

    Q = True
except Exception:
    Q = False

# ---- ledctl libs ----
from ledctl.core import BAUD_DEFAULT, IB_DELAY_DEFAULT
from ledctl.core.core import find_ports
from ledctl.core.setmode import set_builtin_mode
from ledctl.patterns import list_patterns
from ledctl.cli.setpattern import kill_all_patterns  # reuse the helper


BUILTIN_MODES = ("off", "rainbow", "breathing", "cycle", "auto")
PATTERNS_ONLY_B = {"stillred", "stillblue"}  # brightness only
PATTERNS_SPEED = {"breathered"}  # speed presets
PATTERNS_NONE = {"alarm"}  # no args


@dataclass
class LineOpts:
    port: Optional[str] = None
    baud: int = BAUD_DEFAULT
    dtr: bool = True
    rts: bool = False
    delay: float = IB_DELAY_DEFAULT


def _header(lo: LineOpts):
    if not RICH:
        print(
            f"LEDCTL Wizard  |  Port={lo.port or '(auto)'}  Baud={lo.baud}  DTR={lo.dtr}  RTS={lo.rts}"
        )
        return
    table = Table.grid(padding=(0, 1))
    table.add_row("Port", lo.port or "(auto)")
    table.add_row("Baud", str(lo.baud))
    table.add_row("DTR", "ON" if lo.dtr else "OFF")
    table.add_row("RTS", "ON" if lo.rts else "OFF")
    console.print(Panel(table, title="LEDCTL — Wizard", box=ROUNDED, expand=False))


def _select_action() -> str:
    actions = [
        "Set built-in mode",
        "Run custom pattern (background)",
        "Stop running patterns",
        "Settings (port/line)",
        "Quit",
    ]
    if Q:
        return q.select("Choose action:", actions).ask()
    # fallback
    print("\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)))
    i = input("Select> ").strip()
    try:
        idx = int(i) - 1
        return actions[idx]
    except Exception:
        return "Quit"


def _choose_port(current: Optional[str]) -> Optional[str]:
    ports = find_ports() or []
    ports_display = ["(auto)"] + ports
    if Q:
        sel = q.select(
            "Serial port:", ports_display, default=(current or "(auto)")
        ).ask()
        return None if sel == "(auto)" else sel
    # fallback
    print("Ports:")
    for i, p in enumerate(ports_display):
        print(f" {i}) {p}")
    s = input("index> ").strip()
    try:
        idx = int(s)
        sel = ports_display[idx]
        return None if sel == "(auto)" else sel
    except Exception:
        return current


def _settings(lo: LineOpts):
    while True:
        _header(lo)
        if Q:
            choice = q.select(
                "Settings:",
                [
                    f"Port ({lo.port or 'auto'})",
                    f"Baud ({lo.baud})",
                    f"DTR ({'ON' if lo.dtr else 'OFF'})",
                    f"RTS ({'ON' if lo.rts else 'OFF'})",
                    "Back",
                ],
            ).ask()
        else:
            print("1) Port")
            print("2) Baud")
            print("3) DTR toggle")
            print("4) RTS toggle")
            print("5) Back")
            choice = {
                "1": "Port",
                "2": "Baud",
                "3": "DTR",
                "4": "RTS",
                "5": "Back",
            }.get(input("> ").strip(), "Back")

        if choice.startswith("Port") or choice == "Port":
            lo.port = _choose_port(lo.port)
        elif choice.startswith("Baud") or choice == "Baud":
            val = (
                q.text("Baud:", default=str(lo.baud)).ask()
                if Q
                else input("Baud> ").strip()
            )
            try:
                lo.baud = int(val)
            except:
                pass
        elif choice.startswith("DTR") or choice == "DTR":
            lo.dtr = not lo.dtr
        elif choice.startswith("RTS") or choice == "RTS":
            lo.rts = not lo.rts
        else:
            return


def _apply_builtin(lo: LineOpts):
    if Q:
        mode = q.select("Mode:", list(BUILTIN_MODES), default="off").ask()
    else:
        print("\n".join(f"{i+1}. {m}" for i, m in enumerate(BUILTIN_MODES)))
        try:
            mode = BUILTIN_MODES[int(input("Mode> ").strip()) - 1]
        except Exception:
            mode = "off"

    if mode == "off":
        b = 3
        s = 3
    else:
        if Q:
            b = int(
                q.select(
                    "Brightness (1..5):", [str(i) for i in range(1, 6)], default="3"
                ).ask()
            )
            s = int(
                q.select(
                    "Speed (1..5):", [str(i) for i in range(1, 6)], default="3"
                ).ask()
            )
        else:
            b = int(input("Brightness 1..5 [3]> ") or "3")
            s = int(input("Speed 1..5 [3]> ") or "3")

    # one-shot; no loops here
    set_builtin_mode(
        mode=mode,
        brightness=b,
        speed=s,
        port=lo.port,
        baud=lo.baud,
        dtr=lo.dtr,
        rts=lo.rts,
        ib_delay=lo.delay,
    )
    if RICH:
        console.print(f"[green]Applied[/green] {mode} b={b} s={s}")
    else:
        print(f"Applied {mode} b={b} s={s}")


def _run_pattern_background(lo: LineOpts):
    names = list_patterns()
    if not names:
        print("No patterns available.")
        return

    if Q:
        name = q.select("Pattern:", names).ask()
    else:
        print("\n".join(f"{i+1}. {n}" for i, n in enumerate(names)))
        try:
            name = names[int(input("Pattern> ").strip()) - 1]
        except Exception:
            return

    # figure args quickly
    args = []
    if name in PATTERNS_ONLY_B:
        b = (
            int(
                q.select(
                    "Brightness (1..5):", [str(i) for i in range(1, 6)], default="1"
                ).ask()
            )
            if Q
            else int(input("Brightness 1..5 [1]> ") or "1")
        )
        args += ["-b", str(b)]
    elif name in PATTERNS_SPEED:
        s = (
            int(
                q.select(
                    "Speed preset (1..4):", [str(i) for i in range(1, 5)], default="1"
                ).ask()
            )
            if Q
            else int(input("Speed 1..4 [1]> ") or "1")
        )
        args += ["-s", str(s)]
    elif name in PATTERNS_NONE:
        pass
    else:
        # generic: offer brightness/speed quickly
        if Q:
            if q.confirm("Set brightness?", default=False).ask():
                b = int(
                    q.select(
                        "Brightness (1..5):", [str(i) for i in range(1, 6)], default="3"
                    ).ask()
                )
                args += ["-b", str(b)]
            if q.confirm("Set speed?", default=False).ask():
                s = int(
                    q.select(
                        "Speed (1..5):", [str(i) for i in range(1, 6)], default="3"
                    ).ask()
                )
                args += ["-s", str(s)]
        else:
            pass

    # Always kill existing pattern loops before starting a new one
    killed = kill_all_patterns()
    if killed and RICH:
        console.print(f"[yellow]Stopped {killed} running pattern(s)[/yellow]")
    elif killed:
        print(f"Stopped {killed} running pattern(s)")

    # Build command for background run
    cmd = [sys.executable, "-m", "ledctl", "setpattern", name] + args
    # pass line opts (port/baud/dtr/rts/delay)
    if lo.port:
        cmd += ["-p", lo.port]
    cmd += ["-B", str(lo.baud)]
    if lo.dtr:
        cmd += ["-t"]
    else:
        cmd += ["-T"]
    if lo.rts:
        cmd += ["-r"]
    else:
        cmd += ["-R"]
    cmd += ["-d", str(lo.delay)]

    # detach
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setsid,
        close_fds=True,
    )

    if RICH:
        console.print(
            f"[green]Started[/green] pattern [bold]{name}[/bold] in background"
        )
    else:
        print(f"Started pattern {name} in background")


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl wiz",
        description="Small wizard to set built-in modes or start/stop custom patterns.",
    )
    # allow initial line opts (overridable in Settings)
    p.add_argument("--port")
    p.add_argument("--baud", type=int, default=BAUD_DEFAULT)
    p.add_argument("--dtr", action="store_true", default=True)
    p.add_argument("--no-dtr", dest="dtr", action="store_false")
    p.add_argument("--rts", action="store_true", default=False)
    p.add_argument("--no-rts", dest="rts", action="store_false")
    p.add_argument("--delay", type=float, default=IB_DELAY_DEFAULT)
    a = p.parse_args(argv)

    lo = LineOpts(port=a.port, baud=a.baud, dtr=a.dtr, rts=a.rts, delay=a.delay)

    if not Q and RICH:
        console.print(
            "[dim](Tip: install 'questionary' for nicer pickers: pip install questionary)[/dim]"
        )

    while True:
        _header(lo)
        act = _select_action()
        if act == "Set built-in mode":
            _apply_builtin(lo)
        elif act == "Run custom pattern (background)":
            _run_pattern_background(lo)
        elif act == "Stop running patterns":
            n = kill_all_patterns()
            msg = f"Stopped {n} pattern process(es)"
            console.print(f"[yellow]{msg}[/yellow]") if RICH else print(msg)
        elif act == "Settings (port/line)":
            _settings(lo)
        else:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
