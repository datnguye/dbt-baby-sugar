"""A Textual driver that tolerates running off the main thread.

dbt owns the main thread, so the app runs on a daemon thread (see
``SugarAppDriver``). Textual's POSIX driver registers signal handlers
(``SIGTSTP``/``SIGCONT`` for Ctrl+Z suspend, ``SIGWINCH`` for terminal resize)
across its constructor and application-mode start/stop. Python only allows
``signal.signal`` on the main thread, so off it every one of those calls raises
``ValueError: signal only works in main thread`` and the app dies.

This driver makes ``signal.signal`` a harmless no-op for the duration of those
methods, but ONLY when we're off the main thread. On the main thread it behaves
exactly like the stock driver — suspend and live-resize still work. Off it we
forgo those (a fine trade for a UI that lives only for one dbt run); Textual
falls back to polling-based resize detection, so the layout still tracks the
terminal.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from unittest import mock

from textual.drivers.linux_driver import LinuxDriver

_SIGNAL_TARGET = "textual.drivers.linux_driver.signal.signal"


def _noop_signal(*_args: object, **_kwargs: object) -> None:
    return None


def _off_main_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


class ThreadSafeLinuxDriver(LinuxDriver):
    @contextlib.contextmanager
    def _tolerate_off_main(self) -> Iterator[None]:
        """Make ``signal.signal`` a no-op while off the main thread, where it would
        otherwise raise; on the main thread behave exactly like the stock driver."""
        if _off_main_thread():
            with mock.patch(_SIGNAL_TARGET, _noop_signal):
                yield
        else:
            yield

    def __init__(self, *args: object, **kwargs: object) -> None:
        with self._tolerate_off_main():
            super().__init__(*args, **kwargs)

    def start_application_mode(self) -> None:
        with self._tolerate_off_main():
            super().start_application_mode()

    def stop_application_mode(self) -> None:
        with self._tolerate_off_main():
            super().stop_application_mode()
