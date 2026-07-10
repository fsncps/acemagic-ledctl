import argparse
import time

from ledctl.cli.common import make_serial_parser
from ledctl.core import BAUD_DEFAULT, LedCtl, MODES, MODE_NAMES, find_ports
from ledctl.daemon import kill_running_pattern

ALL_MODES = ["NONE"] + MODE_NAMES
NUM_SLOTS = 5

F_MODE = 0
F_DURATION = 1
F_HZ = 2
F_BRIGHT = 3
F_SPEED = 4
NUM_FIELDS = 5

ROW_FIRST_SLOT = 0
ROW_PLAY = NUM_SLOTS
ROW_QUIT = NUM_SLOTS + 1
NUM_ROWS = NUM_SLOTS + 2

COL_MARKER = 2
COL_MODE = 6
COL_DUR = 19
COL_HZ = 27
COL_BRIGHT = 34
COL_SPEED = 43


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="ledctl-pattern-wiz",
        description="Live pattern sequencer TUI — cycle up to 5 modes with custom timing.",
        parents=[make_serial_parser()],
    )
    return p.parse_args(argv)


def tui(dev, dtr, rts, delay):
    try:
        import curses
    except Exception:
        print("curses not available.")
        return

    ports = find_ports()
    if not ports:
        print("No serial device found.")
        return

    port = dev if dev in ports else ports[0]
    ctl = LedCtl(port=port, baud=BAUD_DEFAULT, ib_delay=delay, dtr=dtr, rts=rts)
    ctl.open()

    slots = [
        {"mode": 0, "duration": 2.0, "hz": 0, "brightness": 3, "speed": 3} for _ in range(NUM_SLOTS)
    ]

    ui = {"sel_row": 0, "sel_col": F_MODE}
    play = {"active": False, "slot": 0, "slot_start": 0.0, "last_frame": -1.0}

    def active_slots():
        return [i for i in range(NUM_SLOTS) if slots[i]["mode"] != 0]

    def cycle_time():
        return sum(slots[i]["duration"] for i in active_slots())

    def send_frame(slot):
        mode_idx = slot["mode"]
        if mode_idx == 0:
            return
        mode_val = MODES[MODE_NAMES[mode_idx - 1]]
        ctl.set_mode_once(mode_val, slot["brightness"], slot["speed"])

    def advance():
        act = active_slots()
        if not act:
            play["active"] = False
            return
        cur = play["slot"]
        for _ in range(NUM_SLOTS):
            cur = (cur + 1) % NUM_SLOTS
            if cur in act:
                break
        play["slot"] = cur
        play["slot_start"] = time.monotonic()
        play["last_frame"] = -1.0

    def start_playback():
        act = active_slots()
        if not act:
            return
        play["active"] = True
        play["slot"] = act[0]
        play["slot_start"] = time.monotonic()
        play["last_frame"] = -1.0

    def fmt_field(slot, field):
        if slot["mode"] == 0:
            return "---"
        if field == F_MODE:
            return ALL_MODES[slot["mode"]]
        if field == F_DURATION:
            return f"{slot['duration']:.1f}s"
        if field == F_HZ:
            return f"{slot['hz']}"
        if field == F_BRIGHT:
            return f"{slot['brightness']}"
        if field == F_SPEED:
            return f"{slot['speed']}"
        return ""

    def draw(stdscr):
        stdscr.erase()

        h, w = stdscr.getmaxyx()
        if h < NUM_ROWS + 5 or w < 52:
            stdscr.addstr(0, 0, "Terminal too small (need 52x12 min).")
            stdscr.refresh()
            return

        status = "PLAYING" if play["active"] else "PAUSED "
        line1 = "PATTERN WIZ  ^v:slot  <>:change  TAB:field  SPACE:play  q:quit"
        stdscr.addstr(0, 0, line1[:w])

        cyctime = f"{cycle_time():.1f}s" if active_slots() else "—"
        play_info = ""
        if play["active"] and slots[play["slot"]]["mode"] != 0:
            remaining = max(
                0, slots[play["slot"]]["duration"] - (time.monotonic() - play["slot_start"])
            )
            play_info = f"  Slot {play['slot'] + 1} ({remaining:.1f}s)"

        line2 = (
            f"[{status}]{play_info}  Cycle:{cyctime}  "
            f"DTR:{'ON' if dtr else 'OFF'}  RTS:{'ON' if rts else 'OFF'}"
        )
        stdscr.addstr(1, 0, line2[:w])

        hdr = "       Mode         Dur    Hz   Bright Speed"
        stdscr.addstr(3, 0, hdr[:w])

        for i in range(NUM_SLOTS):
            y = 4 + i
            slot = slots[i]
            marker = ">" if (play["active"] and i == play["slot"]) else " "
            is_sel = ui["sel_row"] == i

            prefix = f"{marker}{i + 1}:"
            stdscr.addstr(y, COL_MARKER, prefix)

            positions = [
                (COL_MODE, F_MODE, 12),
                (COL_DUR, F_DURATION, 6),
                (COL_HZ, F_HZ, 5),
                (COL_BRIGHT, F_BRIGHT, 6),
                (COL_SPEED, F_SPEED, 5),
            ]

            for cx, fidx, width in positions:
                val = fmt_field(slot, fidx)
                attr = 0
                if is_sel and fidx == ui["sel_col"]:
                    attr = curses.A_REVERSE
                stdscr.addstr(y, cx, f"{val:<{width}}", attr)

        btn_y = 4 + NUM_SLOTS + 1
        btn_play = "[Stop]" if play["active"] else "[Play]"
        btn_quit = "[Quit]"

        if ui["sel_row"] == ROW_PLAY:
            stdscr.addstr(btn_y, 2, btn_play, curses.A_REVERSE)
        else:
            stdscr.addstr(btn_y, 2, btn_play)
        stdscr.addstr(btn_y, 9, "  ")
        if ui["sel_row"] == ROW_QUIT:
            stdscr.addstr(btn_y, 11, btn_quit, curses.A_REVERSE)
        else:
            stdscr.addstr(btn_y, 11, btn_quit)

        stdscr.refresh()

    def handle_left_right(step):
        if ui["sel_row"] >= NUM_SLOTS:
            return
        slot = slots[ui["sel_row"]]
        if slot["mode"] == 0 and ui["sel_col"] != F_MODE:
            return
        if ui["sel_col"] == F_MODE:
            slot["mode"] = (slot["mode"] + step) % len(ALL_MODES)
        elif ui["sel_col"] == F_DURATION:
            slot["duration"] = max(0.5, min(30.0, round(slot["duration"] + step * 0.5, 1)))
        elif ui["sel_col"] == F_HZ:
            slot["hz"] = max(0, min(100, slot["hz"] + step))
        elif ui["sel_col"] == F_BRIGHT:
            slot["brightness"] = max(1, min(5, slot["brightness"] + step))
        elif ui["sel_col"] == F_SPEED:
            slot["speed"] = max(1, min(5, slot["speed"] + step))

    def main_loop(stdscr):
        curses.curs_set(0)
        stdscr.timeout(50)
        draw(stdscr)

        while True:
            now = time.monotonic()

            if play["active"]:
                slot = slots[play["slot"]]
                if slot["mode"] == 0:
                    advance()
                    draw(stdscr)
                    continue
                if now - play["slot_start"] >= slot["duration"]:
                    advance()
                    draw(stdscr)
                    continue
                hz = slot["hz"]
                if hz == 0:
                    if play["last_frame"] < play["slot_start"]:
                        send_frame(slot)
                        play["last_frame"] = now
                else:
                    interval = 1.0 / hz
                    if (
                        play["last_frame"] < play["slot_start"]
                        or now - play["last_frame"] >= interval
                    ):
                        send_frame(slot)
                        play["last_frame"] = now

            key = stdscr.getch()

            if key == -1:
                draw(stdscr)
                continue

            if key in (ord("q"), ord("Q")):
                break
            elif key == ord(" "):
                if play["active"]:
                    play["active"] = False
                else:
                    start_playback()
            elif key == curses.KEY_UP:
                ui["sel_row"] = (ui["sel_row"] - 1) % NUM_ROWS
            elif key == curses.KEY_DOWN:
                ui["sel_row"] = (ui["sel_row"] + 1) % NUM_ROWS
            elif key == ord("\t"):
                if ui["sel_row"] < NUM_SLOTS:
                    ui["sel_col"] = (ui["sel_col"] + 1) % NUM_FIELDS
            elif key == curses.KEY_LEFT:
                handle_left_right(-1)
            elif key == curses.KEY_RIGHT:
                handle_left_right(1)
            elif key in (curses.KEY_ENTER, 10, 13):
                if ui["sel_row"] == ROW_PLAY:
                    if play["active"]:
                        play["active"] = False
                    else:
                        start_playback()
                elif ui["sel_row"] == ROW_QUIT:
                    break

            draw(stdscr)

    try:
        curses.wrapper(main_loop)
    finally:
        ctl.close()


def main(argv=None):
    args = parse_args(argv)
    kill_running_pattern()
    tui(args.port, args.dtr, args.rts, args.ib_delay)
    return 0


if __name__ == "__main__":
    main()
