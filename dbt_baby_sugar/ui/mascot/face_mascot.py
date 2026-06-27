"""The animated face mascot for the overview panel.

A little round block-glyph face that emotes with the run. It walks back and forth
across a track in the top-right of the panel and never stops moving; its eyes,
mouth and colour change with the run's mood — calm while running, wide-eyed on
warnings, alarmed on errors, beaming on success, crestfallen on failure, and
sleepy-blinking with a "…" bubble while dbt is still compiling.

Three stacked rows: a domed top, an eyes row, and a mouth row, each two cells
wide inside a ``▌ ▐`` frame. Kept framework-light (only Rich ``Text``) so it can
be unit-tested directly and reused by whatever surface displays it. Purely
emotional support for staring at a long dbt run.
"""

from __future__ import annotations

from rich.text import Text

from dbt_baby_sugar.ui.mascot.mascot_mood import MascotMood

FACE_TOP = " ▛▀▀▜"
FACE_BLINK_EYES = "--"

FACE_TRACK = 12
BLINK_BEAT = 4

WAIT_THOUGHT = (".  ", ".. ", "...", " ..", "  .", "   ")

_MOOD_FACE = {
    MascotMood.WAITING: ("··", "··", "bold grey70"),
    MascotMood.RUNNING: ("••", "◡◡", "bold green"),
    MascotMood.WORRIED: ("◔◔", "~~", "bold yellow"),
    MascotMood.ALARMED: ("◉◉", "оо", "bold red"),
    MascotMood.SUCCESS: ("^^", "◡◡", "bold bright_green"),
    MascotMood.FAILED: ("xx", "‸‸", "bold red"),
}


class FaceMascot:
    """A stateful, animated block-glyph face drawn as a multi-line Rich ``Text``.

    Each ``frame(mood)`` call advances an internal clock and returns the next
    pose. The face always walks across the track; ``mood`` chooses its eyes,
    mouth and colour, blinks the running moods on their own beat, and gives the
    waiting mood a cycling "…" thought bubble.
    """

    def __init__(self) -> None:
        self._frame = 0

    def frame(self, mood: MascotMood = MascotMood.RUNNING) -> Text:
        eyes, mouth, style = _MOOD_FACE[mood]
        if not mood.is_done and self._frame % BLINK_BEAT == 2:
            eyes = FACE_BLINK_EYES
        top_gutter, face_gutter = self._wait_gutters(mood)
        pad = "" if mood.is_waiting else " " * self._walk_offset()
        self._frame += 1
        rows = (
            f"{pad}{top_gutter}{FACE_TOP}".rstrip(),
            f"{pad}{face_gutter} ▌{eyes}▐",
            f"{pad}{face_gutter} ▌{mouth}▐",
        )
        return Text("\n".join(rows), style=style)

    def _wait_gutters(self, mood: MascotMood) -> tuple[str, str]:
        """Left gutters that sit the cycling "…" thought bubble to the LEFT of the
        face while waiting. Returns (top_gutter, face_gutter) of equal width: the
        bubble fills the top row's gutter, blank space pads the other rows so the
        face columns stay aligned."""
        if not mood.is_waiting:
            return "", ""
        thought = WAIT_THOUGHT[self._frame % len(WAIT_THOUGHT)]
        gutter = f"{thought} "
        return gutter, " " * len(gutter)

    def _walk_offset(self) -> int:
        """Position along the track this frame: a ping-pong 0..TRACK..0 walk."""
        span = FACE_TRACK
        pos = self._frame % (2 * span)
        return pos if pos <= span else 2 * span - pos
