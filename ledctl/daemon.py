"""Background-pattern daemon support.

Patterns (stillred, stillblue, ...) work by repeatedly re-sending mode frames
to interrupt the LED firmware's natural mode progression.  They need a running
process.  ``ledctl setpattern`` detaches that loop from the terminal so it persists
until the next ``ledctl`` command kills it.

PID file at ``PID_FILE`` tracks the single background pattern.  ``ledctl off``,
``ledctl setmode``, ``ledctl setpattern``, and ``ledctl wiz`` all call
``kill_running_pattern()`` before opening the serial port — otherwise the
background pattern would keep re-sending and override the new command.
"""

import os
import signal
import sys
import time

PID_FILE = "/tmp/ledctl-pattern.pid"

# Time to let the LED controller's UART parser reset after the pattern process
# is killed.  Without this, the pattern's last partial frame leaves the parser
# mid-frame; the next command's leading bytes get consumed to complete it,
# swallowing the first command and requiring a second invocation.
PORT_SETTLE_DELAY = 0.2


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def remove_pid_file():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def read_pid():
    """Return the PID of a running background pattern, or None.

    Stale PID files (process no longer alive) are cleaned up automatically.
    """
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None
    if not _is_running(pid):
        remove_pid_file()
        return None
    return pid


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def kill_running_pattern(timeout: float = 2.0):
    """SIGTERM any running background pattern and wait for it to die.

    Escalates to SIGKILL after *timeout* seconds.  Cleans up stale PID files.
    No-op when no pattern is running.
    """
    pid = read_pid()
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        remove_pid_file()
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_running(pid):
            break
        time.sleep(0.05)
    if _is_running(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    remove_pid_file()
    time.sleep(PORT_SETTLE_DELAY)


def daemonize():
    """Detach from the controlling terminal via a standard double-fork.

    The parent process exits immediately so the shell prompt returns; the
    grandchild continues running the pattern loop.
    """
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    if devnull > 2:
        os.close(devnull)


def install_sigterm_handler():
    """Raise KeyboardInterrupt on SIGTERM so pattern loops clean up.

    Patterns catch ``KeyboardInterrupt`` to exit their ``while True`` loop;
    the ``with LedCtl`` context then closes the serial port cleanly.
    """

    def _handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handler)
