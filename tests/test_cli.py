import pytest
from ledctl.cli.setmode import parse_args as parse_setmode
from ledctl.cli.off import parse_args as parse_off


def test_setmode_parse_args():
    args = parse_setmode(["rainbow", "-b", "3", "-s", "2"])
    assert args.name == "rainbow"
    assert args.brightness == 3
    assert args.speed == 2


def test_setmode_default_args():
    args = parse_setmode(["cycle"])
    assert args.name == "cycle"
    assert args.brightness == 1
    assert args.speed == 1


def test_off_parse_args():
    args = parse_off([])
    assert args.port is None
    assert args.baud == 10000


def test_setmode_invalid_mode():
    with pytest.raises(SystemExit):
        parse_setmode(["invalid"])
