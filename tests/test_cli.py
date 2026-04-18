from ledctl.cli.off import parse_args as off_parse_args
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


def test_parse_args_auto():
    args = parse_args(["--mode", "auto"])
    assert args.mode == "auto"


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
    assert _resolve_mode(args) == 0x01


def test_resolve_mode_auto():
    args = parse_args(["--mode", "auto"])
    assert _resolve_mode(args) == MODE.AUTO
    assert _resolve_mode(args) == 0x05


def test_resolve_mode_num():
    args = parse_args(["--mode-num", "0x10"])
    assert _resolve_mode(args) == 0x10


def test_resolve_mode_defaults_to_cycle():
    args = parse_args([])
    assert _resolve_mode(args) == MODE.CYCLE


def test_off_parse_args_defaults():
    args = off_parse_args([])
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False


def test_off_parse_args_with_port():
    args = off_parse_args(["--port", "/dev/ttyUSB0"])
    assert args.port == "/dev/ttyUSB0"


def test_wiz_scan_parse_args():
    from ledctl.cli.wizard import parse_args as wiz_parse_args

    args = wiz_parse_args(["scan", "--from", "0x06", "--to", "0x1F", "--hold-ms", "800"])
    assert args.m_from == 0x06
    assert args.m_to == 0x1F
    assert args.hold_ms == 800


def test_wiz_set_parse_args():
    from ledctl.cli.wizard import parse_args as wiz_parse_args

    args = wiz_parse_args(["set", "off", "-b", "5", "-s", "3"])
    assert args.mode == "off"
    assert args.brightness == 5
    assert args.speed == 3


def test_wiz_main_accepts_argv(capsys):
    from ledctl.cli.wizard import main as wiz_main

    wiz_main(["list"])
    out = capsys.readouterr().out
    assert "rainbow: 0x01" in out
    assert "off: 0x04" in out


def test_main_no_args_defaults_to_wiz(monkeypatch):
    from unittest.mock import MagicMock

    import ledctl.__main__ as mod

    mock_wiz = MagicMock()
    monkeypatch.setattr(mod, "wizard_main", mock_wiz)

    monkeypatch.setattr("sys.argv", ["ledctl"])
    mod.main()

    mock_wiz.assert_called_once_with([])
