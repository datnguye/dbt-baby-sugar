"""The mutable run model: the single source of truth the renderer reads."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.node_status import NodeStatus
from dbt_baby_sugar.core.run_phase import RunPhase
from dbt_baby_sugar.core.run_summary import RunSummary


class RunState:
    def __init__(self, models: Iterable[ModelRun] | None = None) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, ModelRun] = {}
        self.summary = RunSummary()
        for model in models or ():
            self._models[model.unique_id] = model

    def _ensure(self, unique_id: str, name: str | None = None) -> ModelRun:
        model = self._models.get(unique_id)
        if model is None:
            model = ModelRun(unique_id=unique_id, name=name or unique_id)
            self._models[unique_id] = model
        model.seen = True
        return model

    def add(self, model: ModelRun) -> None:
        with self._lock:
            self._models.setdefault(model.unique_id, model)

    def merge_dag(self, models: Iterable[ModelRun]) -> None:
        """Graft DAG structure (``depends_on``, real names) onto the live state.

        For a cold first run there is no ``manifest.json`` yet, so models arrive
        from events with no edges and "up next"/"waiting on" stay blank. Once dbt
        writes the manifest mid-run we replay it through here: existing records
        keep their phase/status/timing and only gain their dependencies; unknown
        nodes join as still-unseen queued placeholders so they can surface up
        next without inflating the touched-node count.
        """
        with self._lock:
            for incoming in models:
                existing = self._models.get(incoming.unique_id)
                if existing is None:
                    self._models[incoming.unique_id] = incoming
                    continue
                existing.depends_on = incoming.depends_on
                if existing.name == existing.unique_id:
                    existing.name = incoming.name

    def start(self, unique_id: str, name: str | None = None) -> None:
        with self._lock:
            model = self._ensure(unique_id, name)
            model.phase = RunPhase.RUNNING

    def finish(
        self,
        unique_id: str,
        status: str,
        elapsed: float | None = None,
        index: int | None = None,
        total: int | None = None,
        message: str | None = None,
        name: str | None = None,
    ) -> None:
        with self._lock:
            model = self._ensure(unique_id, name)
            node_status = NodeStatus.from_dbt(status)
            model.phase = RunPhase.SKIPPED if node_status is NodeStatus.SKIPPED else RunPhase.DONE
            model.status = node_status
            model.elapsed = elapsed
            for attr, value in (("index", index), ("total", total), ("message", message)):
                if value is not None:
                    setattr(model, attr, value)
            self.summary.record(node_status)

    def skip(self, unique_id: str, name: str | None = None) -> None:
        with self._lock:
            model = self._ensure(unique_id, name)
            model.phase = RunPhase.SKIPPED
            model.status = NodeStatus.SKIPPED
            self.summary.record(NodeStatus.SKIPPED)

    def note(self, unique_id: str, message: str, name: str | None = None) -> None:
        with self._lock:
            self._ensure(unique_id, name).message = message

    def _blocking_models(self, model: ModelRun) -> list[ModelRun]:
        return [
            upstream
            for dep in model.depends_on
            if (upstream := self._models.get(dep)) is not None and not upstream.finished
        ]

    def _blockers(self, model: ModelRun) -> list[str]:
        return sorted(m.name for m in self._blocking_models(model))

    def _imminence(self, model: ModelRun) -> tuple[int, int, int]:
        """Sort key for "up next": nodes about to unblock come first.

        The closest queued node is one waiting directly behind the running front —
        every remaining blocker is already *running*, so it unblocks the instant
        they finish. Rank:

        1. nodes with no blocker still merely queued (all blockers running) first,
        2. among those, prefer the ones that actually have a running blocker to
           wait on over free roots that have nothing running ahead of them,
        3. then fewest total blockers.

        So mid-run the models waiting on a running upstream lead; roots only lead
        at the very start, before anything is running for them to follow.
        """
        blockers = self._blocking_models(model)
        still_queued = sum(1 for m in blockers if m.phase is RunPhase.QUEUED)
        has_running_blocker = any(m.phase is RunPhase.RUNNING for m in blockers)
        return still_queued, 0 if has_running_blocker else 1, len(blockers)

    def waiting_on(self, unique_id: str) -> list[str]:
        with self._lock:
            model = self._models.get(unique_id)
            return self._blockers(model) if model is not None else []

    def running(self) -> list[ModelRun]:
        """The nodes dbt is executing right now, in stable name order."""
        with self._lock:
            active = [m for m in self._models.values() if m.phase is RunPhase.RUNNING]
            active.sort(key=lambda m: m.name)
            return active

    def upcoming(self, limit: int) -> list[ModelRun]:
        """The queued nodes about to unblock — those waiting on a *running* upstream.

        "Up next" means imminent, not merely ready: a node whose only blocker is
        already running surfaces ahead of a root that has no running upstream to
        wait on, and ahead of nodes still buried behind queued chains. See
        ``_imminence`` for the ranking; name only breaks ties.

        The manifest seeds the whole project DAG, but an invocation runs only its
        selection (``dbt run`` skips seeds, ``--select`` narrows further). dbt
        never lists the selected set, but it does report the run size. Once dbt has
        accounted for that whole size — the run is complete — the leftover queued
        nodes are manifest phantoms, never part of this run, so there is nothing
        up next. See [[progress-denominator-from-dbt-total]] for ``run_total``.
        """
        with self._lock:
            if self._is_complete():
                return []
            pending = [m for m in self._models.values() if m.phase is RunPhase.QUEUED]
            pending.sort(key=lambda m: (*self._imminence(m), m.name))
            return pending[:limit]

    def _reported_max(self) -> int | None:
        reported = [m.total for m in self._models.values() if m.total is not None]
        return max(reported) if reported else None

    def _seen_count(self) -> int:
        return sum(1 for m in self._models.values() if m.seen)

    def _done_count(self) -> int:
        return sum(1 for m in self._models.values() if m.seen and m.finished)

    def _is_complete(self) -> bool:
        run_total = self._reported_max()
        return run_total is not None and self._done_count() >= run_total

    @property
    def total(self) -> int:
        with self._lock:
            return self._seen_count()

    @property
    def run_total(self) -> int:
        """dbt's run-wide node count (the ``N`` in ``of N``), stable for the run.

        dbt stamps every result event with the total it's going to execute. We
        surface the largest one seen so the progress denominator settles on the
        real target instead of creeping up as nodes are discovered. Before the
        first result lands we fall back to the count of nodes touched so far.
        """
        with self._lock:
            reported_max = self._reported_max()
            return reported_max if reported_max is not None else self._seen_count()

    @property
    def done(self) -> int:
        with self._lock:
            return self._done_count()

    @property
    def is_done(self) -> bool:
        """Whether the run has finished, by dbt's reported denominator.

        The single source of truth for "is the run over" that the renderer and
        the mascot both read, so the panel, the verdict line and the mascot's
        mood can never disagree about when to switch to the done state.
        """
        return bool(self.run_total and self.done >= self.run_total)

    @property
    def queued(self) -> int:
        with self._lock:
            return sum(1 for m in self._models.values() if m.phase is RunPhase.QUEUED)

    def __iter__(self) -> Iterator[ModelRun]:
        with self._lock:
            snapshot = [m for m in self._models.values() if m.seen]
        return iter(snapshot)
