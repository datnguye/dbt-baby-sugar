from __future__ import annotations

from pathlib import Path

from dbt_baby_sugar.core.manifest import ManifestReader
from dbt_baby_sugar.core.node_status import NodeStatus
from dbt_baby_sugar.core.run_phase import RunPhase
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.events.event_handler import SugarEventHandler
from tests.unit.conftest import (
    RecordingRenderer,
    make_concurrency_msg,
    make_finished_msg,
    make_message_msg,
    make_other_msg,
    make_result_msg,
    make_skip_msg,
    make_start_msg,
)


def _handler(run_state: RunState) -> tuple[SugarEventHandler, RecordingRenderer]:
    renderer = RecordingRenderer()
    return SugarEventHandler(run_state, renderer), renderer


def test_start_then_finish_updates_state(run_state: RunState) -> None:
    handler, renderer = _handler(run_state)
    handler(make_start_msg("model.p.stg_orders", "stg_orders"))
    handler(make_finished_msg("model.p.stg_orders", "stg_orders", "success", 0.42))
    assert run_state.done == 1
    assert len(renderer.updates) == 2


def test_result_event_captures_index_total_and_message(run_state: RunState) -> None:
    handler, _ = _handler(run_state)
    handler(
        make_result_msg(
            "LogTestResult",
            "model.p.fct_orders",
            "fct_orders",
            "fail",
            execution_time=0.2,
            index=2,
            total=9,
            msg="FAIL 3",
        )
    )
    model = next(m for m in run_state if m.unique_id == "model.p.fct_orders")
    assert model.status is NodeStatus.ERROR
    assert model.index == 2 and model.total == 9
    assert model.message == "FAIL 3"


def test_skip_event_marks_skipped(run_state: RunState) -> None:
    handler, _ = _handler(run_state)
    handler(make_skip_msg("model.p.fct_orders", "fct_orders"))
    model = next(m for m in run_state if m.unique_id == "model.p.fct_orders")
    assert model.phase is RunPhase.SKIPPED


def test_skip_event_without_node_info_is_ignored(run_state: RunState) -> None:
    handler, renderer = _handler(run_state)
    handler(make_skip_msg("", "", with_node_info=False))
    assert run_state.summary.skipped == 0
    assert len(renderer.updates) == 1


def test_message_event_annotates_node(run_state: RunState) -> None:
    handler, _ = _handler(run_state)
    handler(make_message_msg("model.p.stg_orders", "stg_orders", "Database Error: boom"))
    model = next(m for m in run_state if m.unique_id == "model.p.stg_orders")
    assert model.message == "Database Error: boom"


def test_message_event_without_node_info_is_ignored() -> None:
    state = RunState()
    handler, _ = _handler(state)
    msg = make_message_msg("x", "x", "")
    del msg.data.node_info
    handler(msg)
    assert state.total == 0


def test_concurrency_event_sets_summary_header(run_state: RunState) -> None:
    handler, _ = _handler(run_state)
    handler(make_concurrency_msg(4, "dev"))
    assert run_state.summary.threads == 4
    assert run_state.summary.target == "dev"


def test_unhandled_event_is_ignored(run_state: RunState) -> None:
    handler, renderer = _handler(run_state)
    handler(make_other_msg())
    assert run_state.done == 0
    assert renderer.updates == []


def test_handler_without_renderer(run_state: RunState) -> None:
    handler = SugarEventHandler(run_state)
    handler(make_start_msg("model.p.stg_orders", "stg_orders"))
    assert any(m.name == "stg_orders" for m in run_state)


def test_finish_falls_back_to_run_result_status_and_time() -> None:
    state = RunState()
    handler = SugarEventHandler(state)
    handler(make_finished_msg("model.p.x", "x", "success", 0.5))
    model = next(iter(state))
    assert model.status is NodeStatus.SUCCESS
    assert model.elapsed == 0.5


def test_lazy_manifest_seed_restores_up_next_on_cold_start(manifest_dir: Path) -> None:
    # Cold first run: no DAG seeded, so the handler holds a reader and grafts the
    # manifest on at the first node event — restoring waiting-on.
    state = RunState()
    handler = SugarEventHandler(state, manifest_reader=ManifestReader(manifest_dir))
    assert state.waiting_on("model.p.fct_orders") == []
    handler(make_start_msg("model.p.stg_orders", "stg_orders"))
    assert state.waiting_on("model.p.fct_orders") == ["stg_orders"]


def test_lazy_manifest_seed_runs_only_once(manifest_dir: Path) -> None:
    state = RunState()
    reader = ManifestReader(manifest_dir)
    handler = SugarEventHandler(state, manifest_reader=reader)
    calls: list[int] = []
    original = reader.read_models
    reader.read_models = lambda: (calls.append(1), original())[1]
    handler(make_start_msg("model.p.stg_orders", "stg_orders"))
    handler(make_finished_msg("model.p.stg_orders", "stg_orders", "success", 0.1))
    assert len(calls) == 1


def test_unhandled_event_does_not_trigger_manifest_seed(manifest_dir: Path) -> None:
    state = RunState()
    reader = ManifestReader(manifest_dir)
    handler = SugarEventHandler(state, manifest_reader=reader)
    handler(make_other_msg())
    # Ignored events stay off the seed path; the DAG is still unseeded.
    assert state.waiting_on("model.p.fct_orders") == []


def test_finish_falls_back_to_node_status_when_no_result_status(run_state: RunState) -> None:
    handler, _ = _handler(run_state)
    msg = make_result_msg("LogModelResult", "model.p.stg_orders", "stg_orders", "")
    msg.data.status = None
    msg.data.node_info.node_status = "success"
    handler(msg)
    model = next(m for m in run_state if m.unique_id == "model.p.stg_orders")
    assert model.status is NodeStatus.SUCCESS
