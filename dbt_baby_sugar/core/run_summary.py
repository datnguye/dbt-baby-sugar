"""The end-of-run tally that backs dbt's 'Done. PASS=.. WARN=.. ...' line."""

from __future__ import annotations

from dataclasses import dataclass

from dbt_baby_sugar.core.node_status import NodeStatus

_COUNTERS = {
    NodeStatus.SUCCESS: "passed",
    NodeStatus.WARN: "warned",
    NodeStatus.ERROR: "errored",
    NodeStatus.SKIPPED: "skipped",
}


@dataclass
class RunSummary:
    passed: int = 0
    warned: int = 0
    errored: int = 0
    skipped: int = 0
    threads: int | None = None
    target: str | None = None

    @property
    def total(self) -> int:
        return self.passed + self.warned + self.errored + self.skipped

    def record(self, status: NodeStatus) -> None:
        counter = _COUNTERS.get(status)
        if counter is not None:
            setattr(self, counter, getattr(self, counter) + 1)
