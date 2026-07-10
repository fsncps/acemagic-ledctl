from unittest.mock import MagicMock

import pytest

from ledctl.cli.off import parse_args as off_parse_args
from ledctl.cli.setmode import parse_args


def test_parse_args_defaults():
    args = parse_args(["--mode", "cycle"])
    assert args.brightness == 3
    assert args.speed == 3
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


def test_parse_args_auto():
    args = parse_args(["--mode", "auto"])
    assert args.mode == "auto"


def test_setmode_mode_required():
    with pytest.raises(SystemExit):
        parse_args([])


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
    args = parse_args(["--mode", "cycle"])
    assert args.baud == 10000


def test_setmode_parse_args_has_ib_delay_default():
    args = parse_args(["--mode", "cycle"])
    assert args.ib_delay == 0.005


def test_setmode_brightness_choices_rejects_bad():
    with pytest.raises(SystemExit):
        parse_args(["--mode", "cycle", "-b", "9"])


def test_setmode_speed_choices_rejects_bad():
    with pytest.raises(SystemExit):
        parse_args(["--mode", "cycle", "-s", "0"])


def test_setpattern_parse_args_ib_delay():
    from ledctl.cli.setpattern import parse_args as sp_parse_args

    args = sp_parse_args(["--pattern", "alarm", "--delay", "0.003"])
    assert args.ib_delay == 0.003


def test_setpattern_requires_pattern_flag():
    from ledctl.cli.setpattern import parse_args as sp_parse_args

    with pytest.raises(SystemExit):
        sp_parse_args([])


def _mock_daemon(monkeypatch, sp):
    monkeypatch.setattr(sp, "kill_running_pattern", MagicMock())
    monkeypatch.setattr(sp, "daemonize", MagicMock())
    monkeypatch.setattr(sp, "write_pid", MagicMock())
    monkeypatch.setattr(sp, "install_sigterm_handler", MagicMock())
    monkeypatch.setattr(sp, "remove_pid_file", MagicMock())


def test_setpattern_main_forwards_ib_delay(monkeypatch):
    import ledctl.cli.setpattern as sp

    _mock_daemon(monkeypatch, sp)
    mock_run = MagicMock()
    monkeypatch.setattr(sp, "run_pattern", mock_run)
    sp.main(["--pattern", "alarm", "--delay", "0.004"])
    _, kwargs = mock_run.call_args
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
    monkeypatch.setattr(w, "kill_running_pattern", MagicMock())
    rc = w.main(["--baud", "12000"])
    assert rc == 0
    assert called["args"][1] is True  # dtr default


def test_main_no_args_defaults_to_wiz(monkeypatch):
    import ledctl.__main__ as mod

    mock_wiz = MagicMock()
    monkeypatch.setattr(mod, "wizard_main", mock_wiz)

    monkeypatch.setattr("sys.argv", ["ledctl"])
    mod.main()

    mock_wiz.assert_called_once_with([])


# -- pattern-wiz tests --


def test_pattern_wiz_parse_args_defaults():
    from ledctl.cli.pattern_wiz import parse_args

    args = parse_args([])
    assert args.ib_delay == 0.005
    assert args.baud == 10000
    assert args.dtr is True
    assert args.rts is False
    assert args.port is None


def test_pattern_wiz_main_calls_tui(monkeypatch):
    import ledctl.cli.pattern_wiz as pw

    called = {}

    def fake_tui(port, dtr, rts, delay):
        called["args"] = (port, dtr, rts, delay)

    monkeypatch.setattr(pw, "tui", fake_tui)
    monkeypatch.setattr(pw, "kill_running_pattern", MagicMock())
    rc = pw.main(["--baud", "12000"])
    assert rc == 0
    assert called["args"][1] is True


def test_pattern_wiz_main_kills_running_pattern(monkeypatch):
    import ledctl.cli.pattern_wiz as pw

    killed = MagicMock()
    monkeypatch.setattr(pw, "kill_running_pattern", killed)
    monkeypatch.setattr(pw, "tui", MagicMock())
    pw.main([])
    killed.assert_called_once()


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


def test_setpattern_always_daemonizes(monkeypatch):
    import ledctl.cli.setpattern as sp

    _mock_daemon(monkeypatch, sp)
    daemonize_mock = sp.daemonize
    write_pid_mock = sp.write_pid
    sigterm_mock = sp.install_sigterm_handler
    run_mock = MagicMock()
    remove_mock = sp.remove_pid_file
    monkeypatch.setattr(sp, "run_pattern", run_mock)

    sp.main(["--pattern", "alarm"])

    daemonize_mock.assert_called_once()
    write_pid_mock.assert_called_once()
    sigterm_mock.assert_called_once()
    run_mock.assert_called_once()
    remove_mock.assert_called_once()


def test_setpattern_always_kills_existing(monkeypatch):
    import ledctl.cli.setpattern as sp

    _mock_daemon(monkeypatch, sp)
    killed = MagicMock()
    monkeypatch.setattr(sp, "kill_running_pattern", killed)
    monkeypatch.setattr(sp, "run_pattern", MagicMock())
    sp.main(["--pattern", "alarm"])
    killed.assert_called_once()
