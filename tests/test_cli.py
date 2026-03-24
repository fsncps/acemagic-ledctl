from ledctl.cli.setmode import parse_args, _resolve_mode
from ledctl.core import MODE


def test_parse_args_defaults():
    args = parse_args([])
    assert args.brightness == 3
    assert args.speed == 3
    assert args.hz == 0.0
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False


def test_parse_args_with_mode():
    args = parse_args(["--mode", "rainbow", "-b", "5", "-s", "1"])
    assert args.mode == "rainbow"
    assert args.brightness == 5
    assert args.speed == 1


def test_parse_args_mode_num():
    args = parse_args(["--mode-num", "0x03"])
    assert args.mode_num == 0x03


def test_resolve_mode_breath():
    args = parse_args(["--mode", "breath"])
    assert _resolve_mode(args) == MODE.BREATH


def test_resolve_mode_cycle():
    args = parse_args(["--mode", "cycle"])
    assert _resolve_mode(args) == MODE.CYCLE


def test_resolve_mode_off():
    args = parse_args(["--mode", "off"])
    assert _resolve_mode(args) == MODE.OFF


def test_resolve_mode_rainbow():
    args = parse_args(["--mode", "rainbow"])
    assert _resolve_mode(args) == MODE.RAINBOW


def test_resolve_mode_num():
    args = parse_args(["--mode-num", "0x10"])
    assert _resolve_mode(args) == 0x10


def test_resolve_mode_defaults_to_cycle():
    args = parse_args([])
    assert _resolve_mode(args) == MODE.CYCLE
