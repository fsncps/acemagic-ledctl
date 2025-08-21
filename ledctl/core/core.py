# ledctl/core/core.py
from __future__ import annotations

import glob
import time
from types import SimpleNamespace
from typing import Optional, Tuple

try:
    import serial  # pyserial
except ImportError as e:
    raise SystemExit("Missing dependency pyserial. Try: pip install pyserial") from e

BAUD_DEFAULT = 10000
IB_DELAY_DEFAULT = 0.005  # inter-byte delay, seconds

# Device map you confirmed in the wizard:
MODE = SimpleNamespace(
    RAINBOW=0x01,
    BREATH=0x02,
    CYCLE=0x03,
    OFF=0x04,
    AUTO=0x05,
)

# Friendly names -> raw mode bytes
BUILTIN_MODES = {
    "rainbow": MODE.RAINBOW,
    "breathing": MODE.BREATH,
    "cycle": MODE.CYCLE,
    "off": MODE.OFF,
    "auto": MODE.AUTO,
}

# Human 1..5 -> wire 0x05..0x01 (inverted)
LEVEL_TO_WIRE = {1: 0x05, 2: 0x04, 3: 0x03, 4: 0x02, 5: 0x01}


def find_ports():
    """Return a prioritized list of candidate CH340 ports."""
    return (
        sorted(glob.glob("/dev/serial/by-path/*-if00-port0"))
        or sorted(glob.glob("/dev/ttyUSB*"))
        or sorted(glob.glob("/dev/ttyACM*"))
    )


def find_port() -> Optional[str]:
    """Return the first discovered port or None."""
    ports = find_ports()
    return ports[0] if ports else None


def checksum(mode: int, bw: int, sw: int) -> int:
    return (0xFA + mode + bw + sw) & 0xFF


def build_frame(
    mode: int, bright_h: int, speed_h: int
) -> Tuple[int, int, int, int, int]:
    if bright_h not in LEVEL_TO_WIRE or speed_h not in LEVEL_TO_WIRE:
        raise ValueError("brightness/speed must be in 1..5")
    bw = LEVEL_TO_WIRE[bright_h]
    sw = LEVEL_TO_WIRE[speed_h]
    return (0xFA, mode, bw, sw, checksum(mode, bw, sw))


def send_frame_one_shot(
    *,
    port: Optional[str] = None,
    mode: int,
    brightness: int,
    speed: int,
    baud: int = BAUD_DEFAULT,
    dtr: bool = True,
    rts: bool = False,
    ib_delay: float = IB_DELAY_DEFAULT,
) -> None:
    """Open the port, send one frame, close."""
    dev = port or find_port()
    if not dev:
        raise SystemExit("No CH340 tty found (try plugging/replugging).")
    frame = build_frame(mode, brightness, speed)
    srl = serial.Serial(dev, baud, bytesize=8, parity="N", stopbits=1, timeout=1)
    srl.dtr = dtr
    srl.rts = rts
    try:
        for b in frame:
            srl.write(bytes([b]))
            srl.flush()
            time.sleep(ib_delay)
    finally:
        srl.close()


class LedCtl:
    """Context-managed controller that keeps the port open for fast pattern refresh."""

    def __init__(
        self,
        port: Optional[str] = None,
        *,
        baud: int = BAUD_DEFAULT,
        ib_delay: float = IB_DELAY_DEFAULT,
        dtr: bool = True,
        rts: bool = False,
    ):
        self.port = port or find_port()
        if not self.port:
            raise SystemExit("No CH340 tty found (try plugging/replugging).")
        self.baud = baud
        self.ib_delay = ib_delay
        self.dtr = dtr
        self.rts = rts
        self.ser = None

    def open(self):
        if self.ser is None:
            self.ser = serial.Serial(
                self.port, self.baud, bytesize=8, parity="N", stopbits=1, timeout=1
            )
            self.ser.dtr = self.dtr
            self.ser.rts = self.rts

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _write_frame(self, mode: int, bright_h: int, speed_h: int):
        frame = build_frame(mode, bright_h, speed_h)
        for byte in frame:
            self.ser.write(bytes([byte]))
            self.ser.flush()
            time.sleep(self.ib_delay)

    def set_mode_once(self, mode: int, brightness: int = 3, speed: int = 3):
        if self.ser is None:
            self.open()
        self._write_frame(mode, brightness, speed)
