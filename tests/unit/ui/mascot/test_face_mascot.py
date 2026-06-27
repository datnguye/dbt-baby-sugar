from __future__ import annotations

from rich.console import Console

from dbt_baby_sugar.ui.mascot.face_mascot import (
    _MOOD_FACE,
    FACE_BLINK_EYES,
    FACE_TRACK,
    WAIT_THOUGHT,
    FaceMascot,
)
from dbt_baby_sugar.ui.mascot.mascot_mood import MascotMood


def _render(text) -> str:
    console = Console(width=60, force_terminal=False)
    with console.capture() as cap:
        console.print(text)
    return cap.get()


def test_each_mood_renders_its_eyes_and_mouth() -> None:
    for mood, (eyes, mouth, _style) in _MOOD_FACE.items():
        out = _render(FaceMascot().frame(mood))
        assert eyes in out or FACE_BLINK_EYES in out
        assert mouth in out


def test_face_walks_across_the_track() -> None:
    mascot = FaceMascot()
    offsets = {_render(mascot.frame()).splitlines()[0] for _ in range(FACE_TRACK)}
    assert len(offsets) > 1


def test_face_keeps_animating_even_when_done() -> None:
    mascot = FaceMascot()
    frames = {_render(mascot.frame(MascotMood.SUCCESS)) for _ in range(FACE_TRACK)}
    assert len(frames) > 1


def test_running_mood_blinks_within_a_beat() -> None:
    mascot = FaceMascot()
    loop = "".join(_render(mascot.frame()) for _ in range(4))
    assert FACE_BLINK_EYES in loop


def test_waiting_shows_thought_bubble() -> None:
    mascot = FaceMascot()
    loop = "".join(_render(mascot.frame(MascotMood.WAITING)) for _ in range(len(WAIT_THOUGHT)))
    assert "..." in loop
