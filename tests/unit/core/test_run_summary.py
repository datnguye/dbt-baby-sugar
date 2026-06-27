from __future__ import annotations

from dbt_baby_sugar.core.node_status import NodeStatus
from dbt_baby_sugar.core.run_summary import RunSummary


def test_record_tallies_each_status_and_ignores_unknown() -> None:
    summary = RunSummary()
    for status in (
        NodeStatus.SUCCESS,
        NodeStatus.WARN,
        NodeStatus.ERROR,
        NodeStatus.SKIPPED,
        NodeStatus.UNKNOWN,
    ):
        summary.record(status)
    assert (summary.passed, summary.warned, summary.errored, summary.skipped) == (1, 1, 1, 1)
    assert summary.total == 4
