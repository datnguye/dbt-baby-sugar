from __future__ import annotations

import asyncio
import threading

from rich.console import Console
from textual.widgets import RichLog, Static

import dbt_baby_sugar.ui.app.app_driver as app_driver_mod
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.app.app import SugarApp
from dbt_baby_sugar.ui.app.app_driver import SugarAppDriver


def _static_text(app: SugarApp) -> str:
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        console.print(app.overview_content)
    return capture.get()


def test_update_noops_when_app_never_comes_live(monkeypatch) -> None:
    # update() triggers start(), but if the app can't mount it stays not-live and
    # the overview update is dropped rather than raising.
    driver = SugarAppDriver()
    monkeypatch.setattr(driver, "start", lambda: None)  # pretend start did nothing
    driver.update(RunState())
    assert driver._is_live() is False


def test_append_buffers_until_live() -> None:
    driver = SugarAppDriver()
    driver.append("setup line 1")
    driver.append("setup line 2")
    # Captured stdout arriving during dbt setup is buffered, not shown yet.
    assert driver._pending == ["setup line 1", "setup line 2"]


def test_start_spawns_thread_once(monkeypatch) -> None:
    driver = SugarAppDriver()
    monkeypatch.setattr(driver.app, "run", lambda: None)
    monkeypatch.setattr(driver, "_await_mount", lambda: None)
    driver.start()
    first = driver._thread
    driver.start()  # idempotent: second call must not spawn another thread
    assert driver._thread is first
    first.join(timeout=1)


def test_stop_before_start_is_noop() -> None:
    SugarAppDriver().stop()  # nothing running, must not raise


async def test_update_and_append_reach_the_widgets(run_state: RunState) -> None:
    app = SugarApp()
    driver = SugarAppDriver(app=app)
    async with app.run_test() as pilot:
        await pilot.pause()
        run_state.start("model.p.stg_orders")
        await asyncio.to_thread(driver.update, run_state)
        await asyncio.to_thread(driver.append, "08:00:00 PASS stg_orders")
        app._tick()
        await pilot.pause()

        assert "stg_orders" in _static_text(app)
        assert len(app.query_one("#log", RichLog).lines) > 0


async def test_buffered_lines_flush_on_start(run_state: RunState) -> None:
    app = SugarApp()
    driver = SugarAppDriver(app=app)
    # Lines captured before the app comes up are queued...
    driver.append("early setup line")
    async with app.run_test() as pilot:
        await pilot.pause()
        # ...and flushed in order once update() brings the app up.
        await asyncio.to_thread(driver.update, run_state)
        await pilot.pause()
        assert driver._pending == []
        assert len(app.query_one("#log", RichLog).lines) > 0


async def test_stop_exits_the_app() -> None:
    app = SugarApp()
    driver = SugarAppDriver(app=app)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert driver._is_live() is True
        await asyncio.to_thread(driver.stop)
        await pilot.pause()


def test_finish_and_wait_without_thread_is_noop() -> None:
    # No app started (e.g. a parse-only run): finishing must not block or raise.
    SugarAppDriver().finish_and_wait()


def test_await_mount_times_out_when_app_never_starts(monkeypatch) -> None:
    monkeypatch.setattr(app_driver_mod, "MOUNT_TIMEOUT", 0.05)
    monkeypatch.setattr(app_driver_mod, "MOUNT_POLL", 0.01)
    driver = SugarAppDriver()  # app.is_running stays False — loop runs then exits
    driver._await_mount()
    assert driver._is_live() is False


async def test_finish_and_wait_marks_done_then_joins(run_state: RunState) -> None:
    app = SugarApp()
    driver = SugarAppDriver(app=app)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Stand in a finished thread so join() returns immediately.
        driver._thread = threading.Thread(target=lambda: None)
        driver._thread.start()
        await asyncio.to_thread(driver.finish_and_wait)
        await pilot.pause()
        assert app.query_one("#hint", Static).has_class("done")
