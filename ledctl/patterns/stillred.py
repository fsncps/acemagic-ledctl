# #!/usr/bin/env python3
# # T9 PLUS LED: force "solid red" by retriggering CYCLE (starts at red) 4x/sec
# import sys, time, glob
# try:
#     import serial
# except ImportError:
#     sys.exit("pip3 install pyserial")
#
# BAUD = 10000
# IB_DELAY = 0.005           # 5 ms per byte
# MODE_CYCLE = 0x03
# LEVEL_TO_WIRE = {1:0x05, 2:0x04, 3:0x03, 4:0x02, 5:0x01}  # human→wire
#
# def find_port():
#     p = sorted(glob.glob('/dev/serial/by-path/*-if00-port0')) or sorted(glob.glob('/dev/ttyUSB*'))
#     return p[0] if p else None
#
# def send_frame(port, mode, bright_h, speed_h, dtr=True, rts=False):
#     b = LEVEL_TO_WIRE[bright_h]; s = LEVEL_TO_WIRE[speed_h]
#     cs = (0xFA + mode + b + s) & 0xFF
#     ser = serial.Serial(port, BAUD, bytesize=8, parity='N', stopbits=1, timeout=1)
#     ser.dtr = dtr; ser.rts = rts
#     for byte in (0xFA, mode, b, s, cs):
#         ser.write(bytes([byte])); ser.flush(); time.sleep(IB_DELAY)
#     ser.close()
#
# def main():
#     port = find_port()
#     if not port:
#         sys.exit("No CH340 tty found.")
#     print(f"Using {port} @ {BAUD}. Forcing red via CYCLE reset at 4 Hz. Ctrl+C to stop.")
#     interval = 0.025  # 4 Hz
#     bright, speed = 1, 1
#     next_tick = time.monotonic()
#     try:
#         while True:
#             send_frame(port, MODE_CYCLE, bright, speed)  # restarts at red
#             next_tick += interval
#             now = time.monotonic()
#             time.sleep(max(0, next_tick - now))
#     except KeyboardInterrupt:
#         print("\nDone. (Left LEDs as-is.)")
#         # If you prefer turning them off on exit, uncomment:
#         # send_frame(port, 0x04, 3, 3)
#
# if __name__ == "__main__":
#     main()
import time
from ledctl.core import LedCtl, MODE


def run(
    *,
    port=None,
    baud=10000,
    dtr=True,
    rts=False,
    hz: float = None,
    brightness: int = None,
    speed: int = None,
    period: float = None,
    mode_num: int = None,
):
    """
    Force solid red by repeatedly resetting CYCLE. Empirically solid at ~40 Hz.
    """
    hz = 40.0 if hz is None else hz
    brightness = 1 if brightness is None else brightness
    speed = 1 if speed is None else speed
    mode = mode_num if mode_num is not None else MODE.CYCLE

    with LedCtl(port=port, baud=baud, dtr=dtr, rts=rts) as ctl:
        try:
            nxt = time.monotonic()
            interval = 1.0 / hz if hz > 0 else 0.0
            while True:
                ctl.set_mode_once(mode, brightness, speed)
                if interval > 0:
                    nxt += interval
                    time.sleep(max(0, nxt - time.monotonic()))
                else:
                    # one-shot (but pattern defaults to continuous)
                    break
        except KeyboardInterrupt:
            pass
