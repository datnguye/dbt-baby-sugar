from __future__ import annotations

from rich.console import Console
from textual.widgets import RichLog, Static

import dbt_baby_sugar.ui.app.app as app_mod
from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.app.app import SugarApp
from dbt_baby_sugar.ui.app.confirm_cancel import ConfirmCancelScreen


def _as_text(renderable) -> str:
    console = Console(width=100, force_terminal=False)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


async def test_app_mounts_overview_and_log() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        overview = app.query_one("#overview", Static)
        log = app.query_one("#log", RichLog)
        assert overview.border_title == "overview"
        assert log.border_title == "dbt log"
        assert log.max_lines is None  # keeps the whole run's log
        assert log.auto_scroll is True  # follows the tail, wheel scrolls back


async def test_tick_renders_stored_run_state() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        state = RunState([ModelRun("m.a", "stg_orders")])
        state.start("m.a")
        app.set_run_state(state)
        app._tick()
        await pilot.pause()
        overview = app.query_one("#overview", Static)
        assert overview is not None
        assert "stg_orders" in _as_text(app.overview_content)


async def test_overview_animates_on_the_timer_independent_of_events() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        state = RunState([ModelRun("m.a", "stg_orders")])
        state.start("m.a")
        app.set_run_state(state)
        app._tick()
        first = _as_text(app.overview_content)
        app._tick()
        app._tick()
        await pilot.pause()
        assert _as_text(app.overview_content) != first


async def test_tick_without_run_state_is_a_noop() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        app._tick()
        await pilot.pause()
        assert app.overview_content == "(waiting for dbt…)"


async def test_write_log_appends_lines() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        app.write_log("08:00:00 PASS my_model")
        await pilot.pause()
        log = app.query_one("#log", RichLog)
        assert len(log.lines) > 0


async def test_mark_done_switches_hint_and_enter_quits() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.mark_done()
        await pilot.pause()
        hint = app.query_one("#hint", Static)
        assert hint.has_class("done")
        # Enter is bound to quit so the user can dismiss the finished run.
        await pilot.press("enter")


async def test_ctrl_c_opens_confirm_then_no_keeps_running() -> None:
    app = SugarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmCancelScreen)
        await pilot.click("#no")
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmCancelScreen)  # back to the run


async def test_ctrl_c_yes_signals_main_thread_and_exits(monkeypatch) -> None:
    killed: list[int] = []
    monkeypatch.setattr(app_mod.os, "kill", lambda pid, sig: killed.append(sig))
    app = SugarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause()
    assert app_mod.signal.SIGINT in killed  # dbt's main thread was interrupted


def test_on_cancel_choice_noop_when_not_confirmed() -> None:
    # "No"/dismissed path is a pure no-op — safe to call without a running app.
    SugarApp()._on_cancel_choice(False)
    SugarApp()._on_cancel_choice(None)
