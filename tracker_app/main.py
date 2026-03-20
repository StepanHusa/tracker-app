from __future__ import annotations

import argparse
import atexit
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

STATE_DIR = (
    Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    / "tracker_app"
)
PID_FILE = STATE_DIR / "tracker.pid"
LOG_FILE = STATE_DIR / "tracker_app.log"

log = logging.getLogger(__name__)

_window = None  # set by run_app(), used by _toggle_window via idle_add


def main() -> None:
    parser = argparse.ArgumentParser(prog="tracker-app")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start the tracker app in background")
    p_start.add_argument("--no-fork", action="store_true", help="Run in foreground (debug)")

    sub.add_parser("toggle", help="Show/hide the window (starts app if not running)")
    sub.add_parser("stop", help="Quit the running app")

    args = parser.parse_args()

    if args.command == "start":
        _cmd_start(args)
    elif args.command == "toggle":
        _cmd_toggle()
    elif args.command == "stop":
        _cmd_stop()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _cmd_start(args) -> None:
    if not args.no_fork:
        _daemonize()
    _setup_logging(also_stderr=args.no_fork)
    log.info("Starting tracker (pid=%d)", os.getpid())
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _write_pid()
    atexit.register(_cleanup)
    signal.signal(signal.SIGUSR1, _on_sigusr1)
    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigterm)
    _run_app()
    log.info("Tracker exited cleanly")


def _cmd_toggle() -> None:
    pid = _read_pid()
    if pid and _pid_is_alive(pid):
        os.kill(pid, signal.SIGUSR1)
    else:
        # Start the app in background
        script = Path(__file__).parent.parent / "tracker"
        subprocess.Popen(
            [sys.executable, str(script), "start"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _cmd_stop() -> None:
    pid = _read_pid()
    if pid and _pid_is_alive(pid):
        os.kill(pid, signal.SIGTERM)
    else:
        print("tracker-app: not running")


# ---------------------------------------------------------------------------
# App startup (GTK)
# ---------------------------------------------------------------------------

def _run_app() -> None:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    from tracker_app import store
    from tracker_app.window import TrackerWindow

    global _window
    trackers = store.load_all()
    log.info("Loaded %d tracker(s)", len(trackers))
    _window = TrackerWindow(trackers, on_save=store.save, on_delete=store.delete)
    _window.show_all()
    _window.present()
    Gtk.main()


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

def _on_sigusr1(signum, frame) -> None:
    log.debug("Received SIGUSR1 — toggling window")
    from gi.repository import GLib
    GLib.idle_add(_toggle_window)


def _on_sigterm(signum, frame) -> None:
    log.info("Received SIGTERM — shutting down")
    from gi.repository import Gtk
    from gi.repository import GLib
    GLib.idle_add(Gtk.main_quit)


def _toggle_window() -> bool:
    global _window
    if _window is None:
        return False
    if _window.is_visible():
        log.debug("Hiding window")
        _window.hide()
    else:
        log.debug("Showing window")
        _window.show_all()
        _window.present()
    return False  # idle_add: don't repeat


# ---------------------------------------------------------------------------
# Daemon helpers
# ---------------------------------------------------------------------------

def _daemonize() -> None:
    # Double-fork to fully detach from terminal
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    # Redirect stdin/stdout/stderr to /dev/null
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, sys.stdin.fileno())
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    os.close(devnull)


def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _read_pid() -> Optional[int]:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cleanup() -> None:
    log.debug("Cleaning up PID file")
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(also_stderr: bool = False) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    if also_stderr:
        root.addHandler(logging.StreamHandler())
