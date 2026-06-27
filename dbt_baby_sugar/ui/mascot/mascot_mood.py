"""The mascot's mood, derived from the live run status.

WAITING: dbt still parsing/compiling, nothing running yet.
RUNNING: happy, trotting along.
WORRIED: warnings seen, still going.
ALARMED: errors seen mid-run, agitated.
SUCCESS: finished clean, celebrating.
FAILED: finished with errors/skips, slumped.
"""

from __future__ import annotations

from enum import Enum

from dbt_baby_sugar.core.run_phase import RunPhase
from dbt_baby_sugar.core.run_state import RunState


class MascotMood(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    WORRIED = "worried"
    ALARMED = "alarmed"
    SUCCESS = "success"
    FAILED = "failed"

    @classmethod
    def from_run(cls, run_state: RunState) -> MascotMood:
        s = run_state.summary
        if run_state.is_done:
            return cls.FAILED if (s.errored or s.skipped) else cls.SUCCESS
        if s.errored:
            return cls.ALARMED
        if s.warned:
            return cls.WORRIED
        if run_state.done == 0 and not _any_running(run_state):
            return cls.WAITING
        return cls.RUNNING

    @property
    def is_done(self) -> bool:
        return self in (MascotMood.SUCCESS, MascotMood.FAILED)

    @property
    def is_waiting(self) -> bool:
        return self is MascotMood.WAITING


def _any_running(run_state: RunState) -> bool:
    """Whether any node is executing, without the allocate-and-sort of
    ``running()``: a running node is always seen, so a plain scan suffices."""
    return any(m.phase is RunPhase.RUNNING for m in run_state)
