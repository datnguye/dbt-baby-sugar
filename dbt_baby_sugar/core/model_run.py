"""The per-node run record."""

from __future__ import annotations

from dataclasses import dataclass, field

from dbt_baby_sugar.core.node_status import NodeStatus
from dbt_baby_sugar.core.run_phase import RunPhase


@dataclass
class ModelRun:
    unique_id: str
    name: str
    depends_on: frozenset[str] = field(default_factory=frozenset)
    phase: RunPhase = RunPhase.QUEUED
    status: NodeStatus = NodeStatus.UNKNOWN
    elapsed: float | None = None
    index: int | None = None
    total: int | None = None
    message: str | None = None
    seen: bool = False

    @property
    def finished(self) -> bool:
        return self.phase in (RunPhase.DONE, RunPhase.SKIPPED)

    @property
    def succeeded(self) -> bool:
        return self.phase is RunPhase.DONE and self.status is NodeStatus.SUCCESS
