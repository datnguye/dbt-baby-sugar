from __future__ import annotations

from rich.console import Console

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.mascot.face_mascot import FACE_TOP
from dbt_baby_sugar.ui.overview.overview import OverviewFormatter


def _text(run_state: RunState, **kwargs) -> str:
    console = Console(width=100, force_terminal=False)
    with console.capture() as capture:
        console.print(OverviewFormatter(**kwargs).render(run_state))
    return capture.get()


def test_shows_progress_bar_and_tally(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "success", 0.4, index=1, total=2)
    out = _text(run_state)
    assert "1/2 models" in out
    assert "PASS=1 WARN=0 ERROR=0 SKIP=0" in out


def test_tally_with_target_and_threads(run_state: RunState) -> None:
    run_state.summary.threads = 4
    run_state.summary.target = "dev"
    assert "dev | 4 threads" in _text(run_state)


def test_running_section(run_state: RunState) -> None:
    run_state.start("model.p.stg_orders")
    out = _text(run_state)
    assert "running" in out
    assert "stg_orders" in out
    assert "in progress" in out


def test_running_row_shows_elapsed(run_state: RunState) -> None:
    run_state.start("model.p.stg_orders")
    next(m for m in run_state if m.unique_id == "model.p.stg_orders").elapsed = 2.5
    assert "2.5s" in _text(run_state)


def test_up_next_lists_waiting_node(run_state: RunState) -> None:
    run_state.start("model.p.stg_orders")
    out = _text(run_state)
    assert "up next" in out
    assert "fct_orders" in out
    assert "waiting on stg_orders" in out


def test_up_next_shows_queued_when_unblocked(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "success", 0.1)
    out = _text(run_state)
    assert "fct_orders" in out
    assert "queued" in out


def test_no_sections_when_run_complete(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "success", 0.1)
    run_state.finish("model.p.fct_orders", "success", 0.1)
    out = _text(run_state)
    assert "up next" not in out
    assert "running" not in out


def test_sections_size_to_thread_count() -> None:
    models = [ModelRun(f"m.r{i}", f"root_{i}") for i in range(6)]
    state = RunState(models)
    state.summary.threads = 2
    for i in range(2):
        state.start(f"m.r{i}")  # 2 running, 4 queued
    out = _text(state)
    assert {"root_0", "root_1"} <= set(out.split())  # the 2 running nodes
    assert {"root_2", "root_3"} <= set(out.split())  # the next 2 queued nodes
    assert "root_4" not in out  # beyond the 2-row window
    assert "root_5" not in out


def test_sections_fall_back_to_up_next_without_threads(run_state: RunState) -> None:
    run_state.start("model.p.stg_orders")
    assert "up next" in _text(run_state, up_next=1)


def test_overview_includes_face_mascot(run_state: RunState) -> None:
    assert FACE_TOP.strip() in _text(run_state)


def test_mascot_floats_top_right_sharing_lines(run_state: RunState) -> None:
    """The mascot shares the top rows with the content (the bar) — it must not
    consume its own lines above the panel body."""
    run_state.start("model.p.stg_orders")
    console = Console(width=80, force_terminal=False)
    with console.capture() as cap:
        console.print(OverviewFormatter().render(run_state))
    first = cap.get().splitlines()[0]
    assert "models" in first and first.rstrip().endswith(FACE_TOP.strip())


def test_overview_keeps_mascot_when_done(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "success", 0.1, total=2)
    run_state.finish("model.p.fct_orders", "success", 0.1, total=2)
    out = _text(run_state)
    assert FACE_TOP.strip() in out
    assert "completed successfully" in out


def test_overview_outcome_reports_errors_and_skips(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "error", 0.1, total=2)
    run_state.finish("model.p.fct_orders", "skipped", 0.1, total=2)
    out = _text(run_state)
    assert "finished with 1 error(s)" in out
    assert "1 skipped" in out


def test_overview_outcome_errors_without_skips(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "error", 0.1, total=2)
    run_state.finish("model.p.fct_orders", "error", 0.1, total=2)
    out = _text(run_state)
    assert "finished with 2 error(s)" in out
    assert "skipped" not in out
