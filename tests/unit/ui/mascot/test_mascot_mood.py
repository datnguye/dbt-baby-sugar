from __future__ import annotations

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.mascot.mascot_mood import MascotMood


def _state(n: int = 3) -> RunState:
    return RunState([ModelRun(f"m.{i}", f"model_{i}") for i in range(n)])


def test_waiting_before_anything_runs() -> None:
    assert MascotMood.from_run(_state()) is MascotMood.WAITING


def test_running_once_a_node_starts() -> None:
    s = _state()
    s.start("m.0")
    assert MascotMood.from_run(s) is MascotMood.RUNNING


def test_worried_on_warning() -> None:
    s = _state()
    s.finish("m.0", "warn", 0.1, total=3)
    s.start("m.1")
    assert MascotMood.from_run(s) is MascotMood.WORRIED


def test_alarmed_on_error() -> None:
    s = _state()
    s.finish("m.0", "error", 0.1, total=3)
    s.start("m.1")
    assert MascotMood.from_run(s) is MascotMood.ALARMED


def test_success_when_all_done_clean() -> None:
    s = _state(2)
    for i in range(2):
        s.finish(f"m.{i}", "success", 0.1, total=2)
    assert MascotMood.from_run(s) is MascotMood.SUCCESS


def test_failed_when_done_with_errors() -> None:
    s = _state(2)
    s.finish("m.0", "error", 0.1, total=2)
    s.finish("m.1", "skipped", 0.1, total=2)
    assert MascotMood.from_run(s) is MascotMood.FAILED


def test_is_done_and_is_waiting_flags() -> None:
    assert MascotMood.SUCCESS.is_done
    assert MascotMood.FAILED.is_done
    assert not MascotMood.RUNNING.is_done
    assert MascotMood.WAITING.is_waiting
    assert not MascotMood.RUNNING.is_waiting
