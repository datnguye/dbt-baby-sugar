"""The dbt event-bus callback: maps EventMsg payloads to RunState transitions.

Covers the run signals dbt's own log prints — node start/finish, per-resource
result lines (model/test/seed/snapshot/hook/freshness), skips, errors, and the
end-of-run summary — and enriches them with the waiting-on DAG.
"""

from __future__ import annotations

from typing import Any, Protocol

from dbt_baby_sugar.core.manifest import ManifestReader
from dbt_baby_sugar.core.run_state import RunState

START_EVENTS = ("NodeStart", "NodeExecuting", "NodeCompiling")
RESULT_EVENTS = (
    "NodeFinished",
    "LogModelResult",
    "LogTestResult",
    "LogSeedResult",
    "LogSnapshotResult",
    "LogFreshnessResult",
    "LogHookEndLine",
    "LogNodeNoOpResult",
)
SKIP_EVENTS = ("SkippingDetails", "LogSkipBecauseError")
MESSAGE_EVENTS = ("RunResultError", "RunResultWarningMessage", "JinjaLogWarning", "LogStartLine")
SUMMARY_EVENTS = ("ConcurrencyLine",)


class Renderer(Protocol):
    def update(self, run_state: RunState) -> None: ...


class SugarEventHandler:
    """Maps dbt EventMsg names to RunState transitions via a dispatch table.

    Extend coverage by adding ``{event_name: method_name}`` pairs to ``DISPATCH``
    (or overriding it in a subclass) — no change to ``__call__`` is needed.
    """

    DISPATCH = {
        **dict.fromkeys(START_EVENTS, "_on_start"),
        **dict.fromkeys(RESULT_EVENTS, "_on_result"),
        **dict.fromkeys(SKIP_EVENTS, "_on_skip"),
        **dict.fromkeys(MESSAGE_EVENTS, "_on_message"),
        **dict.fromkeys(SUMMARY_EVENTS, "_on_summary"),
    }

    def __init__(
        self,
        run_state: RunState,
        renderer: Renderer | None = None,
        manifest_reader: ManifestReader | None = None,
    ) -> None:
        self.run_state = run_state
        self.renderer = renderer
        self._manifest_reader = manifest_reader
        self._dag_pending = manifest_reader is not None

    def __call__(self, msg: Any) -> None:
        method = self.DISPATCH.get(msg.info.name)
        if method is None:
            return
        self._maybe_seed_dag()
        getattr(self, method)(msg.data)
        self._render()

    def _maybe_seed_dag(self) -> None:
        """Seed the DAG from a manifest that only appears mid-run.

        A cold first run starts with no ``manifest.json``, so the run model has no
        edges and "up next" is blank. dbt writes the manifest during parse, before
        the first node event — so the first dispatched event is our cue to read it
        once and graft the DAG on, restoring up-next and waiting-on. Gated by a
        flag so it runs at most once and stays off the hot per-event path.
        """
        if not self._dag_pending:
            return
        self._dag_pending = False
        self.run_state.merge_dag(self._manifest_reader.read_models())

    def _render(self) -> None:
        if self.renderer is not None:
            self.renderer.update(self.run_state)

    def _on_start(self, data: Any) -> None:
        info = data.node_info
        self.run_state.start(info.unique_id, info.node_name)

    def _on_result(self, data: Any) -> None:
        info = data.node_info
        self.run_state.finish(
            info.unique_id,
            _status_of(data, info),
            elapsed=_elapsed_of(data),
            index=_typed(data, "index", int),
            total=_typed(data, "total", int),
            message=_message_of(data),
            name=info.node_name,
        )

    def _on_skip(self, data: Any) -> None:
        info = _node_info_of(data)
        if info is None:
            return
        self.run_state.skip(info.unique_id, info.node_name)

    def _on_message(self, data: Any) -> None:
        info = _node_info_of(data)
        message = _message_of(data)
        if info is None or not message:
            return
        self.run_state.note(info.unique_id, message, info.node_name)

    def _on_summary(self, data: Any) -> None:
        self.run_state.summary.threads = _typed(data, "num_threads", int)
        self.run_state.summary.target = _typed(data, "target_name", str)


def _node_info_of(data: Any) -> Any | None:
    return getattr(data, "node_info", None)


def _status_of(data: Any, info: Any) -> str:
    status = getattr(data, "status", None)
    if status:
        return str(status)
    run_result = _run_result_of(data)
    if run_result is not None and getattr(run_result, "status", None):
        return str(run_result.status)
    return info.node_status


def _message_of(data: Any) -> str | None:
    for attr in ("msg", "result_message", "description"):
        value = getattr(data, attr, None)
        if value:
            return str(value)
    return None


def _elapsed_of(data: Any) -> float | None:
    direct = _typed(data, "execution_time", float)
    if direct is not None:
        return direct
    run_result = _run_result_of(data)
    return _typed(run_result, "execution_time", float) if run_result else None


def _run_result_of(data: Any) -> Any | None:
    return getattr(data, "run_result", None)


def _typed(data: Any, attr: str, cast: type) -> Any | None:
    value = getattr(data, attr, None)
    return cast(value) if value not in (None, "") else None
