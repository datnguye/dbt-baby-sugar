from __future__ import annotations

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.node_status import NodeStatus
from dbt_baby_sugar.core.run_phase import RunPhase
from dbt_baby_sugar.core.run_state import RunState


def test_start_and_finish_known_node(run_state: RunState) -> None:
    run_state.start("model.p.stg_orders")
    assert run_state.done == 0
    run_state.finish("model.p.stg_orders", "success", 0.4, index=1, total=2, message="OK")
    assert run_state.done == 1
    assert run_state.total == 2
    assert run_state.summary.passed == 1


def test_run_total_uses_dbt_reported_total(run_state: RunState) -> None:
    # The seen-count is 2, but dbt says the run executes 56 nodes.
    run_state.finish("model.p.stg_orders", "success", 0.4, index=1, total=56)
    assert run_state.total == 2  # nodes touched so far
    assert run_state.run_total == 56  # stable run-wide denominator


def test_run_total_falls_back_to_seen_before_first_result(run_state: RunState) -> None:
    # No result has reported a total yet, so we fall back to the seen-count.
    run_state.start("model.p.stg_orders")
    assert run_state.run_total == run_state.total


def test_start_unknown_node_is_added(run_state: RunState) -> None:
    run_state.start("model.p.new", "new_model")
    assert run_state.total == 3


def test_finish_unknown_node_is_added(run_state: RunState) -> None:
    run_state.finish("model.p.ghost", "error")
    assert run_state.total == 3
    assert run_state.done == 1
    assert run_state.summary.errored == 1


def test_finish_with_skipped_status_sets_skipped_phase(run_state: RunState) -> None:
    run_state.finish("model.p.stg_orders", "skipped")
    model = next(m for m in run_state if m.unique_id == "model.p.stg_orders")
    assert model.phase is RunPhase.SKIPPED


def test_skip_marks_node_and_tallies(run_state: RunState) -> None:
    run_state.skip("model.p.fct_orders")
    model = next(m for m in run_state if m.unique_id == "model.p.fct_orders")
    assert model.phase is RunPhase.SKIPPED
    assert model.status is NodeStatus.SKIPPED
    assert run_state.summary.skipped == 1


def test_note_records_message(run_state: RunState) -> None:
    run_state.note("model.p.stg_orders", "compiling...")
    model = next(m for m in run_state if m.unique_id == "model.p.stg_orders")
    assert model.message == "compiling..."


def test_waiting_on_unblocks_on_done_and_skip(run_state: RunState) -> None:
    assert run_state.waiting_on("model.p.fct_orders") == ["stg_orders"]
    run_state.skip("model.p.stg_orders")
    assert run_state.waiting_on("model.p.fct_orders") == []


def test_waiting_on_unknown_node_returns_empty(run_state: RunState) -> None:
    assert run_state.waiting_on("model.p.nope") == []


def test_running_lists_active_nodes_in_name_order(run_state: RunState) -> None:
    run_state.start("model.p.fct_orders")
    run_state.start("model.p.stg_orders")
    assert [m.name for m in run_state.running()] == ["fct_orders", "stg_orders"]
    run_state.finish("model.p.fct_orders", "success", 0.1)
    assert [m.name for m in run_state.running()] == ["stg_orders"]


def test_upcoming_surfaces_next_wave_ordered_by_readiness(run_state: RunState) -> None:
    # The root (stg_orders, 0 blockers) is closest to running, so it ranks ahead
    # of fct_orders, which is still waiting on it.
    upcoming = run_state.upcoming(limit=5)
    assert [m.name for m in upcoming] == ["stg_orders", "fct_orders"]
    assert run_state.queued == 2


def test_upcoming_orders_roots_ahead_of_blocked_nodes() -> None:
    state = RunState(
        [
            ModelRun("m.root", "root"),
            ModelRun("m.a", "a", frozenset({"m.root"})),
            ModelRun("m.b", "b", frozenset({"m.root"})),
        ]
    )
    # The queued root (0 blockers) leads; a and b each still wait on it.
    assert [m.name for m in state.upcoming(limit=5)] == ["root", "a", "b"]
    assert [m.name for m in state.upcoming(limit=1)] == ["root"]
    state.start("m.root")
    # Once the root is running, a and b become the closest queued nodes.
    assert {m.name for m in state.upcoming(limit=5)} == {"a", "b"}


def test_upcoming_prefers_nodes_waiting_on_a_running_upstream() -> None:
    state = RunState(
        [
            ModelRun("m.busy", "busy"),
            ModelRun("m.waiter", "waiter", frozenset({"m.busy"})),
            ModelRun("m.idle_root", "idle_root"),
        ]
    )
    state.start("m.busy")  # busy is running; waiter is one hop behind it
    # waiter (blocked only by a running node) is the true "up next", ahead of the
    # idle root that has nothing running for it to follow.
    assert [m.name for m in state.upcoming(limit=5)] == ["waiter", "idle_root"]


def test_upcoming_ranks_running_blockers_ahead_of_queued_chains() -> None:
    state = RunState(
        [
            ModelRun("m.run", "run"),
            ModelRun("m.near", "near", frozenset({"m.run"})),  # waits on a running node
            ModelRun("m.far_root", "far_root"),
            ModelRun("m.far", "far", frozenset({"m.far_root"})),  # waits on a queued node
        ]
    )
    state.start("m.run")
    ordered = [m.name for m in state.upcoming(limit=5)]
    # near (running blocker) before far_root (idle root) before far (queued blocker).
    assert ordered == ["near", "far_root", "far"]


def test_upcoming_puts_running_downstream_ahead_of_a_free_root() -> None:
    # The screenshot case: a node waiting on a RUNNING model is the true "up next"
    # and must lead a free root that merely happens to have no blockers.
    state = RunState(
        [
            ModelRun("m.busy", "busy"),
            ModelRun("m.downstream", "downstream", frozenset({"m.busy"})),
            ModelRun("m.free_root", "free_root"),
        ]
    )
    state.start("m.busy")
    assert [m.name for m in state.upcoming(limit=5)] == ["downstream", "free_root"]


def test_upcoming_is_empty_once_run_is_complete() -> None:
    # The manifest seeds the whole DAG, but `dbt run` skips the two seeds. They
    # sit QUEUED forever; once dbt has run its 2 models, "up next" must be empty
    # rather than dangling the never-run seeds (the reported bug).
    state = RunState(
        [
            ModelRun("model.p.stg_orders", "stg_orders"),
            ModelRun("model.p.fct_orders", "fct_orders", frozenset({"model.p.stg_orders"})),
            ModelRun("seed.p.raw_orders", "raw_orders"),
            ModelRun("seed.p.raw_customers", "raw_customers"),
        ]
    )
    state.finish("model.p.stg_orders", "success", 0.1, total=2)
    # Mid-run the leftover seeds can still appear; not yet complete.
    assert state.upcoming(limit=5)
    state.finish("model.p.fct_orders", "success", 0.1, total=2)
    # Run is complete (2 of 2 seen-and-finished) — the seeds are phantoms.
    assert state.upcoming(limit=5) == []
    assert state.queued == 2  # the seeds are still technically queued


def test_merge_dag_enriches_event_seeded_nodes_without_losing_progress() -> None:
    # Cold start: fct_orders arrived from an event with no edges and is mid-run.
    state = RunState()
    state.start("model.p.fct_orders", "fct_orders")
    assert state.waiting_on("model.p.fct_orders") == []
    # The manifest lands mid-run and we graft the DAG on.
    state.merge_dag(
        [
            ModelRun("model.p.stg_orders", "stg_orders"),
            ModelRun("model.p.fct_orders", "fct_orders", frozenset({"model.p.stg_orders"})),
        ]
    )
    # Up-next/waiting-on is restored, and fct_orders keeps its RUNNING phase.
    assert state.waiting_on("model.p.fct_orders") == ["stg_orders"]
    fct = next(m for m in state if m.unique_id == "model.p.fct_orders")
    assert fct.phase is RunPhase.RUNNING


def test_merge_dag_adds_unknown_nodes_as_unseen_placeholders() -> None:
    state = RunState()
    state.merge_dag([ModelRun("model.p.future", "future")])
    # The grafted node does not count as touched until an event marks it seen.
    assert state.total == 0
    assert state.queued == 1


def test_merge_dag_fills_placeholder_name_from_manifest() -> None:
    # A node first seen via an event with no name falls back to its unique_id;
    # the manifest later supplies the real name.
    state = RunState()
    state.start("model.p.stg_orders")
    state.merge_dag([ModelRun("model.p.stg_orders", "stg_orders")])
    model = next(iter(state))
    assert model.name == "stg_orders"


def test_add_is_idempotent() -> None:
    state = RunState()
    state.add(ModelRun("model.p.a", "a", seen=True))
    state.add(ModelRun("model.p.a", "renamed", seen=True))
    members = list(state)
    assert len(members) == 1
    assert members[0].name == "a"


def test_iteration_yields_only_seen_models() -> None:
    state = RunState(
        [
            ModelRun("model.p.run", "run", seen=True),
            ModelRun("model.p.unselected", "unselected"),
        ]
    )
    assert {m.name for m in state} == {"run"}
    assert state.total == 1
    state.start("model.p.unselected")
    assert {m.name for m in state} == {"run", "unselected"}


def test_finished_and_succeeded_flags() -> None:
    model = ModelRun("model.p.a", "a", phase=RunPhase.DONE, status=NodeStatus.SUCCESS)
    assert model.succeeded and model.finished
    model.status = NodeStatus.ERROR
    assert not model.succeeded and model.finished
    skipped = ModelRun("model.p.b", "b", phase=RunPhase.SKIPPED, status=NodeStatus.SKIPPED)
    assert skipped.finished and not skipped.succeeded
