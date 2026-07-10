from ledctl.core import (
    BAUD_DEFAULT,
    IB_DELAY_DEFAULT,
    LEVEL_TO_WIRE,
    MODE,
    MODE_NAMES,
    MODES,
    find_port,
    find_ports,
)


def test_level_to_wire():
    assert LEVEL_TO_WIRE[1] == 0x05
    assert LEVEL_TO_WIRE[5] == 0x01
    assert len(LEVEL_TO_WIRE) == 5


def test_mode_constants():
    assert MODE.RAINBOW == 0x01
    assert MODE.BREATH == 0x02
    assert MODE.CYCLE == 0x03
    assert MODE.OFF == 0x04
    assert MODE.AUTO == 0x05


def test_mode_values_sequential():
    values = [MODE.RAINBOW, MODE.BREATH, MODE.CYCLE, MODE.OFF, MODE.AUTO]
    assert values == [0x01, 0x02, 0x03, 0x04, 0x05]


def test_baud_default():
    assert BAUD_DEFAULT == 10000


def test_ib_delay_default():
    assert IB_DELAY_DEFAULT == 0.005


def test_find_port_returns_string_or_none():
    result = find_port()
    assert result is None or isinstance(result, str)


def test_checksum_calculation():
    for mode_val in [MODE.RAINBOW, MODE.BREATH, MODE.CYCLE, MODE.OFF, MODE.AUTO]:
        bright_wire = LEVEL_TO_WIRE[3]
        speed_wire = LEVEL_TO_WIRE[3]
        expected = (0xFA + mode_val + bright_wire + speed_wire) & 0xFF
        assert expected == (0xFA + mode_val + 0x03 + 0x03) & 0xFF


def test_level_mapping_inverted():
    assert LEVEL_TO_WIRE[1] > LEVEL_TO_WIRE[5]
    assert LEVEL_TO_WIRE[3] == 0x03


def test_find_ports_returns_list():
    result = find_ports()
    assert isinstance(result, list)


def test_find_ports_entries_are_strings():
    for p in find_ports():
        assert isinstance(p, str)


def test_find_port_matches_find_ports_first():
    ports = find_ports()
    assert find_port() == (ports[0] if ports else None)


def test_mode_names_registry():
    assert MODES["rainbow"] == MODE.RAINBOW == 0x01
    assert MODES["breathing"] == MODE.BREATH == 0x02
    assert MODES["cycle"] == MODE.CYCLE == 0x03
    assert MODES["off"] == MODE.OFF == 0x04
    assert MODES["auto"] == MODE.AUTO == 0x05
    assert set(MODE_NAMES) == set(MODES.keys())
