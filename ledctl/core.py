import glob
import time
from types import SimpleNamespace
from typing import Optional

try:
    import serial  # pyserial
except ImportError as e:
    raise SystemExit("Missing dependency pyserial. Try: pip install pyserial") from e

BAUD_DEFAULT = 10000
IB_DELAY_DEFAULT = 0.005  # inter-byte delay, seconds

MODE = SimpleNamespace(
    RAINBOW=0x01,
    BREATH=0x02,
    CYCLE=0x03,
    OFF=0x04,
    AUTO=0x05,
)

LEVEL_TO_WIRE = {1: 0x05, 2: 0x04, 3: 0x03, 4: 0x02, 5: 0x01}

MODES = {
    "rainbow": MODE.RAINBOW,
    "breathing": MODE.BREATH,
    "cycle": MODE.CYCLE,
    "off": MODE.OFF,
    "auto": MODE.AUTO,
}
MODE_NAMES = list(MODES.keys())


def find_ports() -> list:
    """Return all candidate CH340/tty ports, deterministically ordered."""
    return (
        sorted(glob.glob("/dev/serial/by-path/*-if00-port0"))
        or sorted(glob.glob("/dev/ttyUSB*"))
        or sorted(glob.glob("/dev/ttyACM*"))
    )


def find_port() -> Optional[str]:
    """Find a single CH340 port deterministically (first match or None)."""
    return (find_ports() or [None])[0]


class LedCtl:
    """
    Minimal controller that keeps the port open for fast pattern refresh.
    """

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
        if self.ser:
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
        if bright_h not in LEVEL_TO_WIRE or speed_h not in LEVEL_TO_WIRE:
            raise ValueError("brightness/speed must be in 1..5")
        b = LEVEL_TO_WIRE[bright_h]
        s = LEVEL_TO_WIRE[speed_h]
        frame = [0xFA, mode, b, s]
        cs = (sum(frame)) & 0xFF
        frame.append(cs)
        for byte in frame:
            self.ser.write(bytes([byte]))
            self.ser.flush()
            time.sleep(self.ib_delay)

    def set_mode_once(self, mode: int, brightness: int = 3, speed: int = 3):
        self._write_frame(mode, brightness, speed)
