import pytest
from ledctl.core import checksum, build_frame, LEVEL_TO_WIRE
from ledctl.core.setmode import resolve_mode


def test_checksum():
    assert checksum(0x01, 0x05, 0x05) == (0xFA + 0x01 + 0x05 + 0x05) & 0xFF


def test_build_frame():
    frame = build_frame(0x01, 1, 1)
    assert frame[0] == 0xFA
    assert len(frame) == 5


def test_build_frame_invalid_brightness():
    with pytest.raises(ValueError, match="brightness"):
        build_frame(0x01, 6, 1)


def test_build_frame_invalid_speed():
    with pytest.raises(ValueError, match="speed"):
        build_frame(0x01, 1, 0)


def test_level_to_wire():
    assert LEVEL_TO_WIRE[1] == 0x05
    assert LEVEL_TO_WIRE[5] == 0x01


def test_resolve_mode_string():
    assert resolve_mode("rainbow") == 0x01
    assert resolve_mode("breathing") == 0x02
    assert resolve_mode("cycle") == 0x03


def test_resolve_mode_int():
    assert resolve_mode(0x01) == 0x01


def test_resolve_mode_invalid():
    with pytest.raises(SystemExit):
        resolve_mode("invalid_mode")
