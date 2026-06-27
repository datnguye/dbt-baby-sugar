from __future__ import annotations

import pytest

from dbt_baby_sugar.core.node_status import NodeStatus


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("success", NodeStatus.SUCCESS),
        ("PASS", NodeStatus.SUCCESS),
        ("warn", NodeStatus.WARN),
        ("error", NodeStatus.ERROR),
        ("fail", NodeStatus.ERROR),
        ("skipped", NodeStatus.SKIPPED),
        ("weird", NodeStatus.UNKNOWN),
        (None, NodeStatus.UNKNOWN),
    ],
)
def test_from_dbt(raw: str | None, expected: NodeStatus) -> None:
    assert NodeStatus.from_dbt(raw) is expected
