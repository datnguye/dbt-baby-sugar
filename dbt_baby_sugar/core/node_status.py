"""Normalised terminal outcome of a node, derived from dbt's node_status strings."""

from __future__ import annotations

from enum import Enum


class NodeStatus(str, Enum):
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"

    @classmethod
    def from_dbt(cls, status: str | None) -> NodeStatus:
        if status is None:
            return cls.UNKNOWN
        return _DBT_STATUS_MAP.get(status.strip().lower(), cls.UNKNOWN)


_DBT_STATUS_ALIASES = {
    NodeStatus.SUCCESS: ("success", "pass", "passed"),
    NodeStatus.WARN: ("warn", "warning"),
    NodeStatus.ERROR: ("error", "fail", "failed", "runtime error"),
    NodeStatus.SKIPPED: ("skipped", "skip"),
}
_DBT_STATUS_MAP = {
    alias: status for status, aliases in _DBT_STATUS_ALIASES.items() for alias in aliases
}
