import os
import signal
from unittest.mock import patch

import ledctl.daemon as d


def test_read_pid_no_file():
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-nonexistent.pid"):
        assert d.read_pid() is None


def test_read_pid_stale(monkeypatch):
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-stale.pid"):
        d.write_pid()
        # simulate the process dying
        monkeypatch.setattr(d, "_is_running", lambda pid: False)
        assert d.read_pid() is None
        # stale PID file should have been cleaned up
        assert not os.path.exists("/tmp/ledctl-test-stale.pid")


def test_write_and_read_pid():
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-rw.pid"):
        d.write_pid()
        assert d.read_pid() == os.getpid()
        d._remove_pid_file()


def test_remove_pid_file_missing_is_noop():
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-noop.pid"):
        d._remove_pid_file()  # should not raise


def test_kill_running_pattern_no_pid_file():
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-nopid.pid"):
        d.kill_running_pattern()  # should not raise


def test_kill_running_pattern_stale():
    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-killstale.pid"):
        d.write_pid()
        with patch("ledctl.daemon._is_running", return_value=False):
            d.kill_running_pattern()
        assert not os.path.exists("/tmp/ledctl-test-killstale.pid")


def test_kill_running_pattern_kills(monkeypatch):
    kills = []
    pid = 99999

    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-kills.pid"):
        with open("/tmp/ledctl-test-kills.pid", "w") as f:
            f.write(str(pid))

        monkeypatch.setattr(d, "read_pid", lambda: pid)
        monkeypatch.setattr(d, "_is_running", lambda p: False)
        monkeypatch.setattr("os.kill", lambda sig_pid, sig: kills.append((sig_pid, sig)))

        d.kill_running_pattern()
        assert (pid, signal.SIGTERM) in kills
        assert not os.path.exists("/tmp/ledctl-test-kills.pid")


def test_kill_running_pattern_escalates_to_sigkill(monkeypatch):
    kills = []
    pid = 99999
    times = iter([0.0, 1.0])  # deadline=0.01; 1.0 > 0.01 → loop never enters

    with patch("ledctl.daemon.PID_FILE", "/tmp/ledctl-test-sigkill.pid"):
        with open("/tmp/ledctl-test-sigkill.pid", "w") as f:
            f.write(str(pid))

        monkeypatch.setattr(d, "read_pid", lambda: pid)
        monkeypatch.setattr(d, "_is_running", lambda p: True)
        monkeypatch.setattr("os.kill", lambda sig_pid, sig: kills.append((sig_pid, sig)))
        monkeypatch.setattr("time.sleep", lambda _: None)
        monkeypatch.setattr("time.monotonic", lambda: next(times))

        d.kill_running_pattern(timeout=0.01)
        assert (pid, signal.SIGTERM) in kills
        assert (pid, signal.SIGKILL) in kills
        assert not os.path.exists("/tmp/ledctl-test-sigkill.pid")
