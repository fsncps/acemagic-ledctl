from ledctl.core import LEVEL_TO_WIRE, MODE, BAUD_DEFAULT, IB_DELAY_DEFAULT, find_port


def test_level_to_wire():
    assert LEVEL_TO_WIRE[1] == 0x05
    assert LEVEL_TO_WIRE[5] == 0x01
    assert len(LEVEL_TO_WIRE) == 5


def test_mode_constants():
    assert MODE.BREATH == 0x02
    assert MODE.CYCLE == 0x03
    assert MODE.OFF == 0x04
    assert MODE.RAINBOW == 0x05


def test_baud_default():
    assert BAUD_DEFAULT == 10000


def test_ib_delay_default():
    assert IB_DELAY_DEFAULT == 0.005


def test_find_port_returns_string_or_none():
    result = find_port()
    assert result is None or isinstance(result, str)


def test_checksum_calculation():
    assert (0xFA + MODE.CYCLE + LEVEL_TO_WIRE[3] + LEVEL_TO_WIRE[3]) & 0xFF == (
        0xFA + 0x03 + 0x03 + 0x03
    ) & 0xFF


def test_level_mapping_inverted():
    assert LEVEL_TO_WIRE[1] > LEVEL_TO_WIRE[5]
    assert LEVEL_TO_WIRE[3] == 0x03
