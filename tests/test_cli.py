from unittest.mock import MagicMock

import pytest

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


def test_parse_args_breathing():
    args = parse_args(["--mode", "breathing"])
    assert args.mode == "breathing"


def test_parse_args_breath_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--mode", "breath"])  # hard rename, no alias


def test_parse_args_mode_num():
    args = parse_args(["--mode-num", "0x03"])
    assert args.mode_num == 0x03


def test_parse_args_auto():
    args = parse_args(["--mode", "auto"])
    assert args.mode == "auto"


def test_resolve_mode_breathing():
    args = parse_args(["--mode", "breathing"])
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


def test_off_parse_args_has_delay_default():
    args = off_parse_args([])
    assert args.ib_delay == 0.005


def test_off_parse_args_delay_flag():
    args = off_parse_args(["--delay", "0.008"])
    assert args.ib_delay == 0.008


def test_off_parse_args_ib_delay_alias():
    args = off_parse_args(["--ib-delay", "0.002"])
    assert args.ib_delay == 0.002


def test_setmode_parse_args_has_baud_default():
    args = parse_args([])
    assert args.baud == 10000


def test_setmode_parse_args_has_ib_delay_default():
    args = parse_args([])
    assert args.ib_delay == 0.005


def test_setmode_brightness_choices_rejects_bad():
    with pytest.raises(SystemExit):
        parse_args(["-b", "9"])


def test_setmode_speed_choices_rejects_bad():
    with pytest.raises(SystemExit):
        parse_args(["-s", "0"])


def test_setpattern_parse_args_ib_delay():
    from ledctl.cli.setpattern import parse_args as sp_parse_args

    args = sp_parse_args(["alarm", "--delay", "0.003"])
    assert args.ib_delay == 0.003


def test_setpattern_main_forwards_ib_delay(monkeypatch):
    import ledctl.cli.setpattern as sp

    mock = MagicMock()
    monkeypatch.setattr(sp, "run_pattern", mock)
    sp.main(["alarm", "--delay", "0.004"])
    _, kwargs = mock.call_args
    assert kwargs.get("ib_delay") == 0.004


def test_wiz_parse_args_defaults():
    from ledctl.cli.wizard import parse_args

    args = parse_args([])
    assert args.ib_delay == 0.005
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False
    assert args.port is None


def test_wiz_parse_args_rejects_old_subcommand():
    from ledctl.cli.wizard import parse_args

    with pytest.raises(SystemExit):
        parse_args(["set", "off"])  # 'set' no longer exists


def test_wiz_main_calls_tui(monkeypatch):
    import ledctl.cli.wizard as w

    called = {}

    def fake_tui(port, dtr, rts, delay):
        called["args"] = (port, dtr, rts, delay)

    monkeypatch.setattr(w, "tui", fake_tui)
    rc = w.main(["--baud", "12000"])
    assert rc == 0
    assert called["args"][1] is True  # dtr default


def test_main_no_args_defaults_to_wiz(monkeypatch):
    from unittest.mock import MagicMock

    import ledctl.__main__ as mod

    mock_wiz = MagicMock()
    monkeypatch.setattr(mod, "wizard_main", mock_wiz)

    monkeypatch.setattr("sys.argv", ["ledctl"])
    mod.main()

    mock_wiz.assert_called_once_with([])


# -- daemon integration tests --


def test_off_main_kills_running_pattern(monkeypatch):
    import ledctl.cli.off as off_mod

    killed = MagicMock()
    monkeypatch.setattr(off_mod, "kill_running_pattern", killed)
    monkeypatch.setattr(off_mod, "LedCtl", MagicMock())
    off_mod.main([])
    killed.assert_called_once()


def test_setmode_main_kills_running_pattern(monkeypatch):
    import ledctl.cli.setmode as sm_mod

    killed = MagicMock()
    monkeypatch.setattr(sm_mod, "kill_running_pattern", killed)
    monkeypatch.setattr(sm_mod, "LedCtl", MagicMock())
    sm_mod.main(["--mode", "cycle"])
    killed.assert_called_once()


def test_wiz_main_kills_running_pattern(monkeypatch):
    import ledctl.cli.wizard as w

    killed = MagicMock()
    monkeypatch.setattr(w, "kill_running_pattern", killed)
    monkeypatch.setattr(w, "tui", MagicMock())
    w.main([])
    killed.assert_called_once()


def test_setpattern_foreground_no_daemonize(monkeypatch):
    import ledctl.cli.setpattern as sp

    monkeypatch.setattr(sp, "kill_running_pattern", MagicMock())
    daemonize_mock = MagicMock()
    monkeypatch.setattr(sp, "daemonize", daemonize_mock)
    monkeypatch.setattr(sp, "run_pattern", MagicMock())
    sp.main(["alarm"])
    daemonize_mock.assert_not_called()


def test_setpattern_background_calls_daemonize(monkeypatch):
    import ledctl.cli.setpattern as sp

    monkeypatch.setattr(sp, "kill_running_pattern", MagicMock())
    daemonize_mock = MagicMock()
    write_pid_mock = MagicMock()
    sigterm_mock = MagicMock()
    run_mock = MagicMock()
    remove_mock = MagicMock()
    monkeypatch.setattr(sp, "daemonize", daemonize_mock)
    monkeypatch.setattr(sp, "write_pid", write_pid_mock)
    monkeypatch.setattr(sp, "install_sigterm_handler", sigterm_mock)
    monkeypatch.setattr(sp, "run_pattern", run_mock)
    monkeypatch.setattr(sp, "_remove_pid_file", remove_mock)

    sp.main(["alarm", "--background"])

    daemonize_mock.assert_called_once()
    write_pid_mock.assert_called_once()
    sigterm_mock.assert_called_once()
    run_mock.assert_called_once()
    remove_mock.assert_called_once()


def test_setpattern_background_short_flag():
    from ledctl.cli.setpattern import parse_args as sp_parse_args

    args = sp_parse_args(["alarm", "-g"])
    assert args.background is True


def test_setpattern_always_kills_existing(monkeypatch):
    import ledctl.cli.setpattern as sp

    killed = MagicMock()
    monkeypatch.setattr(sp, "kill_running_pattern", killed)
    monkeypatch.setattr(sp, "run_pattern", MagicMock())
    sp.main(["alarm"])
    killed.assert_called_once()
