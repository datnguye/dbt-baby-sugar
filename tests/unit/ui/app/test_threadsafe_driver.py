from __future__ import annotations

import threading
from unittest import mock

from dbt_baby_sugar.ui.app.threadsafe_driver import ThreadSafeLinuxDriver, _noop_signal


def test_noop_signal_returns_none() -> None:
    assert _noop_signal("anything", 1, 2) is None


def _patch_parent():
    # Replace LinuxDriver's lifecycle methods so we can exercise the wrappers
    # without a real terminal or App.
    return (
        mock.patch.object(ThreadSafeLinuxDriver.__bases__[0], "__init__", return_value=None),
        mock.patch.object(ThreadSafeLinuxDriver.__bases__[0], "start_application_mode"),
        mock.patch.object(ThreadSafeLinuxDriver.__bases__[0], "stop_application_mode"),
    )


def test_off_main_thread_wraps_signal_calls() -> None:
    init_p, start_p, stop_p = _patch_parent()
    with init_p as init, start_p as start, stop_p as stop:
        captured = {}

        def run() -> None:
            driver = ThreadSafeLinuxDriver.__new__(ThreadSafeLinuxDriver)
            driver.__init__("app")
            driver.start_application_mode()
            driver.stop_application_mode()
            captured["ran"] = True

        worker = threading.Thread(target=run)
        worker.start()
        worker.join()

    assert init.called and start.called and stop.called


def test_on_main_thread_uses_stock_behavior() -> None:
    init_p, start_p, stop_p = _patch_parent()
    with init_p as init, start_p as start, stop_p as stop:
        driver = ThreadSafeLinuxDriver.__new__(ThreadSafeLinuxDriver)
        driver.__init__("app")  # main thread: no signal patching, straight through
        driver.start_application_mode()
        driver.stop_application_mode()
    assert init.called and start.called and stop.called
