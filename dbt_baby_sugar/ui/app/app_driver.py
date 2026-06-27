"""Runs the Textual app on a background thread and feeds it from dbt's callback.

dbt holds the main thread, so ``App.run()`` (which blocks) goes on a daemon
thread. dbt's event callback and the stdout capture both live on other threads,
so every UI mutation is marshalled onto Textual's loop with ``call_from_thread``.

The app is started LAZILY, on the first update/append — not at activation time.
dbt registers its adapter and warms a ``multiprocessing`` *spawn* pool during
manifest setup, and Python's spawn snapshots the open file descriptors
(``fds_to_keep``). A Textual app running concurrently churns terminal fds, so a
spawn mid-startup captures a now-invalid fd and dbt dies with
``bad value(s) in fds_to_keep``. By the time the first node event reaches us,
that setup (and all its spawning) is done — so starting then sidesteps the clash.

``update`` re-renders the overview from a ``RunState`` snapshot; ``append`` is
the log sink the stdout capture writes each captured line into. Both no-op while
the app is mounting or after it stops, so edge-of-run updates are dropped rather
than raising.
"""

from __future__ import annotations

import atexit
import threading
import time

from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.app.app import SugarApp

MOUNT_TIMEOUT = 5.0
MOUNT_POLL = 0.02


class SugarAppDriver:
    def __init__(self, app: SugarApp | None = None) -> None:
        self.app = app or SugarApp()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._pending: list[str] = []

    def start(self) -> None:
        """Spawn the app thread, block until mounted, then flush buffered log."""
        with self._start_lock:
            if self._thread is not None or self.app.is_running:
                return
            self._thread = threading.Thread(target=self.app.run, daemon=True)
            self._thread.start()
            atexit.register(self.finish_and_wait)
        self._await_mount()
        self._flush_pending()

    def finish_and_wait(self) -> None:
        """Flag the run done, then block until the user closes the window."""
        if self._is_live():
            self.app.call_from_thread(self.app.mark_done)
        if self._thread is not None:
            self._thread.join()

    def _flush_pending(self) -> None:
        if self._is_live() and self._pending:
            backlog, self._pending = self._pending, []
            self.app.call_from_thread(self._write_many, backlog)

    def _write_many(self, lines: list[str]) -> None:
        for line in lines:
            self.app.write_log(line)

    def stop(self) -> None:
        if self._is_live():
            self.app.call_from_thread(self.app.exit)

    def update(self, run_state: RunState) -> None:
        """Hand the latest snapshot to the app, whose repaint timer animates it —
        so the dino's animation is independent of dbt's events. Node events only
        fire after dbt's spawn-based setup, so this is also the safe trigger to
        lazily start the app."""
        self.start()
        if self._is_live():
            self._flush_pending()
            self.app.call_from_thread(self.app.set_run_state, run_state)

    def append(self, line: str) -> None:
        """Sink for captured stdout, which starts flowing DURING dbt's setup.
        Never start the app from here, or we race the spawn; buffer lines until
        update() brings the app up, then they flush in order (see start())."""
        if self._is_live():
            self.app.call_from_thread(self.app.write_log, line)
        else:
            self._pending.append(line)

    def _await_mount(self) -> None:
        deadline = time.monotonic() + MOUNT_TIMEOUT
        while not self.app.is_running and time.monotonic() < deadline:
            time.sleep(MOUNT_POLL)

    def _is_live(self) -> bool:
        return self.app.is_running
