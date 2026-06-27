"""Compatibility canary: drive dbt-baby-sugar from a REAL dbt run.

The unit suite feeds the handler synthetic ``FakeMsg`` payloads, so it proves our
logic but says nothing about whether dbt-core still emits the events and fields we
read. This suite closes that gap: it runs an actual ``dbt build`` on a tiny DuckDB
fixture project with our handler wired onto dbt's live event bus, then asserts the
handler saw real node events and drove ``RunState`` — start to finish, with the DAG
intact. If dbt-core renames ``node_info``, reshapes a result payload, or changes the
``EventManager`` callback API, this is what goes red.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dbt_baby_sugar.core.manifest import ManifestReader
from dbt_baby_sugar.core.run_phase import RunPhase
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.events.event_handler import SugarEventHandler

dbtRunner = pytest.importorskip("dbt.cli.main").dbtRunner
pytest.importorskip("dbt.adapters.duckdb")

pytestmark = pytest.mark.integration

FIXTURE_PROJECT = Path(__file__).parent / "fixture_project"


def _make_handler(target_dir: Path) -> SugarEventHandler:
    """A driver-less handler armed to read the manifest dbt writes mid-run.

    No Textual app and no stdout capture — we only care that real dbt events
    reach the handler and move the run model, which is the compat surface. The
    manifest reader mirrors a cold first run: the DAG is grafted on at the first
    node event (see SugarEventHandler._maybe_seed_dag).
    """
    return SugarEventHandler(RunState(), manifest_reader=ManifestReader(target_dir))


def _invoke_dbt(
    handler: SugarEventHandler, args: list[str], project_dir: Path, target_dir: Path
) -> None:
    """Run dbt with the handler wired onto its event bus.

    dbt clears the event manager's callbacks at the start of every ``invoke`` (see
    ``setup_event_logger``), so the supported way to observe a run is the
    ``dbtRunner(callbacks=...)`` seam — which also exercises the real
    ``EventMsg`` callback signature that the compat check is meant to guard.
    """
    env = {
        "DBT_PROFILES_DIR": str(FIXTURE_PROJECT),
        "SUGAR_DUCKDB_PATH": str(project_dir / "sugar_fixture.duckdb"),
    }
    previous = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        result = dbtRunner(callbacks=[handler]).invoke(
            [*args, "--project-dir", str(FIXTURE_PROJECT), "--target-path", str(target_dir)]
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    assert result.success, f"dbt {args} failed: {result.exception}"


def test_real_build_drives_run_state(tmp_path: Path) -> None:
    target_dir = tmp_path / "target"
    handler = _make_handler(target_dir)
    _invoke_dbt(handler, ["seed"], tmp_path, target_dir)
    _invoke_dbt(handler, ["build", "--select", "stg_orders+"], tmp_path, target_dir)

    state = handler.run_state
    finished = [m for m in state if m.finished]
    assert finished, "no nodes finished — dbt's result events were not understood"
    assert state.done > 0
    assert {m.name for m in state} >= {"stg_orders", "fct_orders"}


def test_real_run_records_dependencies(tmp_path: Path) -> None:
    # The handler lazily reads the manifest dbt writes during parse, so the DAG
    # edge stg_orders -> fct_orders must be visible after a real run.
    target_dir = tmp_path / "target"
    handler = _make_handler(target_dir)
    _invoke_dbt(handler, ["seed"], tmp_path, target_dir)
    _invoke_dbt(handler, ["build", "--select", "stg_orders+"], tmp_path, target_dir)

    state = handler.run_state
    fct = next((m for m in state if m.name == "fct_orders"), None)
    assert fct is not None
    assert fct.phase in (RunPhase.DONE, RunPhase.RUNNING)
    assert any("stg_orders" in dep for dep in fct.depends_on)
