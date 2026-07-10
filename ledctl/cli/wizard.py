import argparse
import time

from ledctl.cli.common import make_serial_parser
from ledctl.core import (
    BAUD_DEFAULT,
    LedCtl,
    MODES,
    MODE_NAMES,
    find_ports,
)
from ledctl.daemon import kill_running_pattern


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-wizard",
        description="Interactive curses TUI for the ACEMAGIC LED controller.",
        parents=[make_serial_parser()],
    )
    return p.parse_args(argv)


# -------- arrow-key TUI (curses) --------
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
        return LedCtl(port=ports[port_idx], baud=BAUD_DEFAULT, ib_delay=delay, dtr=_dtr, rts=_rts)

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

    # Field indices: 0 Port, 1 Mode, 2 Bright, 3 Speed, 4 DTR, 5 RTS, 6 [Apply], 7 [Off], 8 [Blink], 9 [Quit]
    idx = 1  # start at Mode

    def bold_if(stdscr, y, x, text, cond):
        if cond:
            stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, x, text)
        if cond:
            stdscr.attroff(curses.A_BOLD)

    def draw(stdscr):
        stdscr.clear()
        stdscr.addstr(0, 2, "T9 PLUS LED — Arrow keys to change; Enter=Apply; q=Quit")
        bold_if(stdscr, 2, 2, f"Port:       {ports[port_idx]}", idx == 0)
        bold_if(stdscr, 3, 2, f"Mode:       {MODE_NAMES[mode_idx]}", idx == 1)
        bold_if(stdscr, 4, 2, f"Brightness: {bright}  (1..5)", idx == 2)
        bold_if(stdscr, 5, 2, f"Speed:      {speed}  (1..5)", idx == 3)
        bold_if(stdscr, 6, 2, f"DTR:        {'ON' if _dtr else 'OFF'}", idx == 4)
        bold_if(stdscr, 7, 2, f"RTS:        {'ON' if _rts else 'OFF'}", idx == 5)

        # buttons line, bold the selected one
        y = 9
        bold_if(stdscr, y, 2, "[Apply]", idx == 6)
        stdscr.addstr(y, 9, "  ")
        bold_if(stdscr, y, 11, "[Off]", idx == 7)
        stdscr.addstr(y, 17, "  ")
        bold_if(stdscr, y, 19, "[Blink]", idx == 8)
        stdscr.addstr(y, 27, "  ")
        bold_if(stdscr, y, 29, "[Quit]", idx == 9)
        stdscr.refresh()

    def main(stdscr):
        nonlocal idx, port_idx, mode_idx, bright, speed, _dtr, _rts
        curses.curs_set(0)
        draw(stdscr)
        while True:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break
            elif key == curses.KEY_UP:
                idx = (idx - 1) % 10
            elif key == curses.KEY_DOWN:
                idx = (idx + 1) % 10
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                step = -1 if key == curses.KEY_LEFT else 1
                if idx == 0:  # Port
                    on_port_change(step)
                elif idx == 1:  # Mode
                    mode_idx = (mode_idx + step) % len(MODE_NAMES)
                elif idx == 2:  # Brightness
                    bright = min(5, max(1, bright + step))
                elif idx == 3:  # Speed
                    speed = min(5, max(1, speed + step))
                elif idx == 4:  # DTR
                    _dtr = not _dtr
                elif idx == 5:  # RTS
                    _rts = not _rts
            elif key in (curses.KEY_ENTER, 10, 13):
                if idx == 6:
                    apply()
                elif idx == 7:
                    off()
                elif idx == 8:
                    blink_test()
                elif idx == 9:
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


def text_interactive(dev, dtr, rts, delay):
    ports = find_ports()
    if not ports:
        print("No CH340 tty found.")
        return
    port = dev or ports[0]
    cur_mode = "off"
    cur_b = 3
    cur_s = 3
    _dtr, _rts = dtr, rts
    ctl = LedCtl(port=port, baud=BAUD_DEFAULT, ib_delay=delay, dtr=_dtr, rts=_rts)
    ctl.open()
    try:
        try:
            ctl.set_mode_once(
                MODES[cur_mode],
                cur_b,
                cur_s,
            )
        except Exception:
            pass

        def ask(prompt, valid):
            while True:
                v = input(prompt).strip().lower()
                if v in valid:
                    return v

        while True:
            print(
                f"\nPort={port} DTR={int(_dtr)} RTS={int(_rts)}  "
                f"Mode={cur_mode}  Bright={cur_b}  Speed={cur_s}"
            )
            print(
                " [t]heme  [i]ntensity  [s]peed  [a]pply  [b]link  "
                "[p]ort  line-[l] (DTR/RTS)  [o]ff  [q]uit"
            )
            c = input("> ").strip().lower()
            if c == "q":
                break
            elif c == "t":
                print("Modes:", ", ".join(MODE_NAMES))
                cur_mode = ask("mode> ", set(MODE_NAMES))
            elif c == "i":
                cur_b = int(ask("brightness 1..5> ", set(str(x) for x in range(1, 6))))
            elif c == "s":
                cur_s = int(ask("speed 1..5> ", set(str(x) for x in range(1, 6))))
            elif c == "a":
                ctl.set_mode_once(MODES[cur_mode], cur_b, cur_s)
            elif c == "b":
                ctl.set_mode_once(MODES["rainbow"], 5, 2)
                time.sleep(0.2)
                ctl.set_mode_once(MODES["off"], 3, 3)
            elif c == "p":
                ports = find_ports() or ports
                if ports:
                    print("\nPorts:")
                    [print(f" {i}) {p}") for i, p in enumerate(ports)]
                    i = int(ask("index> ", set(str(x) for x in range(len(ports)))))
                    port = ports[i]
                    ctl.close()
                    ctl = LedCtl(port=port, baud=BAUD_DEFAULT, ib_delay=delay, dtr=_dtr, rts=_rts)
                    ctl.open()
            elif c == "l":
                _dtr = not _dtr if input("Toggle DTR? (y/N) ").lower().startswith("y") else _dtr
                _rts = not _rts if input("Toggle RTS? (y/N) ").lower().startswith("y") else _rts
            elif c == "o":
                ctl.set_mode_once(MODES["off"], cur_b, cur_s)
    finally:
        ctl.close()


def main(argv=None):
    args = parse_args(argv)
    kill_running_pattern()
    tui(args.port, args.dtr, args.rts, args.ib_delay)
    return 0


if __name__ == "__main__":
    main()
