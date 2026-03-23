import sys, time, glob, argparse

try:
    import serial
except ImportError:
    sys.exit("Install pyserial:  pip3 install pyserial")

BAUD = 10000
IB_DELAY = 0.005  # 5 ms between bytes

# Protocol: 0xFA, MODE, BRIGHT, SPEED, CHECKSUM ; CHECKSUM = (0xFA + MODE + BRIGHT + SPEED) & 0xFF
MODES = {
    "rainbow": 0x01,
    "breathing": 0x02,
    "cycle": 0x03,
    "off": 0x04,
    "auto": 0x05,
}
MODE_NAMES = list(MODES.keys())
LEVEL_TO_WIRE = {
    1: 0x05,
    2: 0x04,
    3: 0x03,
    4: 0x02,
    5: 0x01,
}  # human 1..5 → wire 0x05..0x01


def find_ports():
    bypath = sorted(glob.glob("/dev/serial/by-path/*-if00-port0"))
    if bypath:
        return bypath
    return sorted(glob.glob("/dev/ttyUSB*"))


def checksum(mode, bright_wire, speed_wire):
    return (0xFA + mode + bright_wire + speed_wire) & 0xFF


def send_frame(dev, mode, bright_h, speed_h, dtr=True, rts=False, delay=IB_DELAY):
    """Send one frame (maps human levels to wire; sets DTR/RTS)."""
    b = LEVEL_TO_WIRE[bright_h]
    s = LEVEL_TO_WIRE[speed_h]
    frame = (0xFA, mode, b, s, checksum(mode, b, s))
    srl = serial.Serial(dev, BAUD, bytesize=8, parity="N", stopbits=1, timeout=1)
    srl.dtr = dtr
    srl.rts = rts
    for byte in frame:
        srl.write(bytes([byte]))
        srl.flush()
        time.sleep(delay)
    srl.close()


def parse_args():
    epilog = """\
Examples:
  ledctl set off
  ledctl set breathing -b 5 -s 5          # slow breathing, intense (brightest & slowest)
  ledctl set cycle -b 3 -s 1              # fast cycle, medium bright
  ledctl blink --a rainbow --b off --on-ms 120 --off-ms 120 --seconds 8
  ledctl pulse --mode breathing --seconds 10 --min 2 --max 5 --speed 3

Notes:
  Levels are 1..5 (human). The device expects inverted values, handled for you:
    brightness 5 → wire 0x01 (max) … brightness 1 → wire 0x05 (min)
    speed 1 (fastest) → wire 0x05 … speed 5 (slowest) → wire 0x01
    """
    p = argparse.ArgumentParser(
        prog="ledctl",
        description="ACEMAGIC T9 PLUS LED controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    p.add_argument(
        "-d", "--dev", default=None, help="serial device (auto-detect if omitted)"
    )
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
    p.add_argument(
        "--no-rts", dest="rts", action="store_false", help="deassert RTS (default)"
    )
    p.add_argument(
        "--delay",
        type=float,
        default=IB_DELAY,
        help="inter-byte delay (sec), default 0.005",
    )

    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("set", help="set a mode once")
    sp.add_argument("mode", choices=MODE_NAMES)
    sp.add_argument("-b", "--brightness", type=int, default=3, choices=range(1, 6))
    sp.add_argument("-s", "--speed", type=int, default=3, choices=range(1, 6))

    sp = sub.add_parser("blink", help="alternate between two states")
    sp.add_argument(
        "--a", dest="mode_a", required=True, choices=MODE_NAMES, help="first mode"
    )
    sp.add_argument(
        "--bmode",
        dest="mode_b",
        default="off",
        choices=MODE_NAMES,
        help="second mode (default: off)",
    )
    sp.add_argument(
        "-b",
        "--brightness",
        type=int,
        default=5,
        choices=range(1, 6),
        help="brightness for both",
    )
    sp.add_argument(
        "-s", "--speed", type=int, default=3, choices=range(1, 6), help="speed for both"
    )
    sp.add_argument("--on-ms", type=int, default=300)
    sp.add_argument("--off-ms", type=int, default=300)
    grp = sp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--times", type=int, help="repeat count")
    grp.add_argument("--seconds", type=float, help="run for N seconds")

    sp = sub.add_parser("pulse", help="sweep brightness up/down")
    sp.add_argument("--mode", default="breathing", choices=MODE_NAMES)
    sp.add_argument("--seconds", type=float, default=6.0)
    sp.add_argument("--min", type=int, default=2, choices=range(1, 6))
    sp.add_argument("--max", type=int, default=5, choices=range(1, 6))
    sp.add_argument("--speed", type=int, default=3, choices=range(1, 6))

    sub.add_parser("list", help="list modes")

    sp = sub.add_parser("scan", help="scan MODE codes (0x01..0x1F default)")
    sp.add_argument("--from", dest="m_from", type=lambda x: int(x, 0), default=0x01)
    sp.add_argument("--to", dest="m_to", type=lambda x: int(x, 0), default=0x1F)
    sp.add_argument("--hold-ms", type=int, default=600)
    sp.add_argument("-b", "--brightness", type=int, default=3, choices=range(1, 6))
    sp.add_argument("-s", "--speed", type=int, default=3, choices=range(1, 6))
    return p.parse_args()


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

    def apply():
        send_frame(
            ports[port_idx],
            MODES[MODE_NAMES[mode_idx]],
            bright,
            speed,
            _dtr,
            _rts,
            delay,
        )

    def off():
        send_frame(ports[port_idx], MODES["off"], bright, speed, _dtr, _rts, delay)

    def blink_test():
        send_frame(ports[port_idx], MODES["rainbow"], 5, 2, _dtr, _rts, delay)
        time.sleep(0.2)
        send_frame(ports[port_idx], MODES["off"], 3, 3, _dtr, _rts, delay)

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
                off()
                break
            elif key == curses.KEY_UP:
                idx = (idx - 1) % 10
            elif key == curses.KEY_DOWN:
                idx = (idx + 1) % 10
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                step = -1 if key == curses.KEY_LEFT else 1
                if idx == 0:  # Port
                    ports[:] = find_ports() or ports
                    if ports:
                        port_idx = (port_idx + step) % len(ports)
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
                    off()
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

    curses.wrapper(main)


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
    try:
        send_frame(port, MODES[cur_mode], cur_b, cur_s, _dtr, _rts, delay)
    except:
        pass

    def ask(prompt, valid):
        while True:
            v = input(prompt).strip().lower()
            if v in valid:
                return v

    while True:
        print(
            f"\nPort={port} DTR={int(_dtr)} RTS={int(_rts)}  Mode={cur_mode}  Bright={cur_b}  Speed={cur_s}"
        )
        print(
            " [t]heme  [i]ntensity  [s]peed  [a]pply  [b]link  [p]ort  line-[l] (DTR/RTS)  [o]ff  [q]uit"
        )
        c = input("> ").strip().lower()
        if c == "q":
            try:
                send_frame(port, MODES["off"], cur_b, cur_s, _dtr, _rts, delay)
            except:
                pass
            break
        elif c == "t":
            print("Modes:", ", ".join(MODE_NAMES))
            cur_mode = ask("mode> ", set(MODE_NAMES))
        elif c == "i":
            cur_b = int(ask("brightness 1..5> ", set(str(x) for x in range(1, 6))))
        elif c == "s":
            cur_s = int(ask("speed 1..5> ", set(str(x) for x in range(1, 6))))
        elif c == "a":
            send_frame(port, MODES[cur_mode], cur_b, cur_s, _dtr, _rts, delay)
        elif c == "b":
            send_frame(port, MODES["rainbow"], 5, 2, _dtr, _rts, delay)
            time.sleep(0.2)
            send_frame(port, MODES["off"], 3, 3, _dtr, _rts, delay)
        elif c == "p":
            ports = find_ports() or ports
            if ports:
                print("\nPorts:")
                [print(f" {i}) {p}") for i, p in enumerate(ports)]
                i = int(ask("index> ", set(str(x) for x in range(len(ports)))))
                port = ports[i]
        elif c == "l":
            _dtr = (
                not _dtr
                if input("Toggle DTR? (y/N) ").lower().startswith("y")
                else _dtr
            )
            _rts = (
                not _rts
                if input("Toggle RTS? (y/N) ").lower().startswith("y")
                else _rts
            )
        elif c == "o":
            send_frame(port, MODES["off"], cur_b, cur_s, _dtr, _rts, delay)


def main():
    a = parse_args()
    dev = a.dev or (find_ports()[0] if find_ports() else None)

    if a.cmd == "list":
        for k, v in MODES.items():
            print(f"{k}: 0x{v:02X}")
        return

    if a.cmd == "set":
        send_frame(dev, MODES[a.mode], a.brightness, a.speed, a.dtr, a.rts, a.delay)
        return

    if a.cmd == "blink":
        end_time = time.monotonic() + a.seconds if a.seconds else None
        count = 0
        try:
            while True:
                send_frame(
                    dev, MODES[a.mode_a], a.brightness, a.speed, a.dtr, a.rts, a.delay
                )
                time.sleep(a.on_ms / 1000.0)
                send_frame(
                    dev, MODES[a.mode_b], a.brightness, a.speed, a.dtr, a.rts, a.delay
                )
                time.sleep(a.off_ms / 1000.0)
                count += 1
                if a.times and count >= a.times:
                    break
                if end_time and time.monotonic() >= end_time:
                    break
        except KeyboardInterrupt:
            pass
        return

    if a.cmd == "pulse":
        lo, hi = min(a.min, a.max), max(a.min, a.max)
        end = time.monotonic() + a.seconds
        up = True
        level = lo
        try:
            while time.monotonic() < end:
                send_frame(dev, MODES[a.mode], level, a.speed, a.dtr, a.rts, a.delay)
                time.sleep(0.15)
                if up:
                    level += 1
                    if level >= hi:
                        up = False
                else:
                    level -= 1
                    if level <= lo:
                        up = True
        except KeyboardInterrupt:
            pass
        return

    # default: interactive arrow-key UI
    tui(dev, a.dtr, a.rts, a.delay)


if __name__ == "__main__":
    main()
