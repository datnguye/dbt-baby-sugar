"""Lifecycle phase of a node within a run."""

from __future__ import annotations

from enum import Enum


class RunPhase(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
