"""Shared fixtures: synthetic dbt EventMsg objects and a sample manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState


@dataclass
class FakeInfo:
    name: str
    level: str = "debug"


@dataclass
class FakeNodeInfo:
    unique_id: str
    node_name: str
    node_status: str = "started"


@dataclass
class FakeRunResult:
    status: str | None = None
    execution_time: float = 0.0


class FakeData:
    def __init__(self, node_info: FakeNodeInfo | None = None, **fields: object) -> None:
        if node_info is not None:
            self.node_info = node_info
        for key, value in fields.items():
            setattr(self, key, value)


@dataclass
class FakeMsg:
    info: FakeInfo
    data: FakeData


def make_start_msg(unique_id: str, name: str) -> FakeMsg:
    return FakeMsg(FakeInfo("NodeStart"), FakeData(FakeNodeInfo(unique_id, name, "started")))


def make_finished_msg(
    unique_id: str,
    name: str,
    status: str,
    elapsed: float,
    *,
    index: int | None = None,
    total: int | None = None,
    event: str = "NodeFinished",
) -> FakeMsg:
    return FakeMsg(
        FakeInfo(event),
        FakeData(
            FakeNodeInfo(unique_id, name, status),
            run_result=FakeRunResult(status, elapsed),
            index=index,
            total=total,
        ),
    )


def make_result_msg(
    event: str,
    unique_id: str,
    name: str,
    status: str,
    *,
    execution_time: float | None = None,
    index: int | None = None,
    total: int | None = None,
    msg: str | None = None,
    result_message: str | None = None,
    description: str | None = None,
) -> FakeMsg:
    return FakeMsg(
        FakeInfo(event),
        FakeData(
            FakeNodeInfo(unique_id, name, status),
            status=status,
            execution_time=execution_time,
            index=index,
            total=total,
            msg=msg,
            result_message=result_message,
            description=description,
        ),
    )


def make_skip_msg(unique_id: str, name: str, *, with_node_info: bool = True) -> FakeMsg:
    node_info = FakeNodeInfo(unique_id, name, "skipped") if with_node_info else None
    return FakeMsg(FakeInfo("SkippingDetails"), FakeData(node_info))


def make_message_msg(unique_id: str, name: str, msg: str) -> FakeMsg:
    return FakeMsg(
        FakeInfo("RunResultError"),
        FakeData(FakeNodeInfo(unique_id, name, "error"), msg=msg),
    )


def make_concurrency_msg(threads: int, target: str) -> FakeMsg:
    return FakeMsg(FakeInfo("ConcurrencyLine"), FakeData(num_threads=threads, target_name=target))


def make_other_msg() -> FakeMsg:
    return FakeMsg(FakeInfo("MainReportVersion"), FakeData(FakeNodeInfo("", "")))


@pytest.fixture
def sample_models() -> list[ModelRun]:
    return [
        ModelRun("model.p.stg_orders", "stg_orders", seen=True),
        ModelRun(
            "model.p.fct_orders",
            "fct_orders",
            frozenset({"model.p.stg_orders"}),
            seen=True,
        ),
    ]


@pytest.fixture
def run_state(sample_models: list[ModelRun]) -> RunState:
    return RunState(sample_models)


@pytest.fixture
def manifest_dir(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    target.mkdir()
    manifest = {
        "nodes": {
            "model.p.stg_orders": {
                "name": "stg_orders",
                "resource_type": "model",
                "depends_on": {"nodes": []},
            },
            "model.p.fct_orders": {
                "name": "fct_orders",
                "resource_type": "model",
                "depends_on": {"nodes": ["model.p.stg_orders"]},
            },
            "test.p.not_null": {
                "name": "not_null",
                "resource_type": "test",
                "depends_on": {"nodes": ["model.p.fct_orders"]},
            },
        }
    }
    (target / "manifest.json").write_text(json.dumps(manifest))
    return target


@dataclass
class RecordingRenderer:
    updates: list = field(default_factory=list)

    def update(self, run_state: RunState) -> None:
        self.updates.append(run_state)
