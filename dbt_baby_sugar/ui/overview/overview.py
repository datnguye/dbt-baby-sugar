"""Pure formatting of the overview panel: mascot, progress bar, tally, running,
up next.

Kept free of any widget or framework type so it can be unit-tested directly and
rendered by whatever surface displays it (the Textual ``Static``). It turns a
``RunState`` snapshot into a Rich ``Text`` block; the widget just shows it.

The animated face mascot in the top-right lives in its own module — see
``dbt_baby_sugar.ui.mascot.face_mascot.FaceMascot``.
"""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.mascot.face_mascot import FACE_TRACK, FaceMascot
from dbt_baby_sugar.ui.mascot.mascot_mood import MascotMood

MASCOT_CELL_WIDTH = FACE_TRACK + 6

BAR_WIDTH = 24
FILLED_BLOCK = "█"
EMPTY_BLOCK = "░"
UP_NEXT = 3

RUNNING_GLYPH = "▶"
QUEUED_GLYPH = "•"
RUNNING_STYLE = "bold green"
QUEUED_STYLE = "yellow"
RUNNING_HEADER_STYLE = "bold green"
UP_NEXT_HEADER_STYLE = "bold yellow"
NAME_WIDTH = 28


class OverviewFormatter:
    def __init__(self, up_next: int = UP_NEXT) -> None:
        self.up_next = up_next
        self._mascot = FaceMascot()

    def render(self, run_state: RunState) -> RenderableType:
        lines: list[Text] = [
            self._bar(run_state),
            self._tally(run_state),
        ]
        if run_state.is_done:
            lines.append(self._outcome(run_state))
            return self._with_mascot(Group(*lines), run_state)
        rows = self._section_size(run_state)
        running = run_state.running()[:rows]
        if running:
            lines.append(Text("running", style=RUNNING_HEADER_STYLE))
            lines += [self._running_row(m) for m in running]
        upcoming = run_state.upcoming(rows)
        if upcoming:
            lines.append(Text("up next", style=UP_NEXT_HEADER_STYLE))
            lines += [self._upcoming_row(run_state, m) for m in upcoming]
        return self._with_mascot(Group(*lines), run_state)

    def _outcome(self, run_state: RunState) -> Text:
        """A single verdict line that replaces the running/up-next sections once
        finished, so the now-compact panel still says how the run went."""
        s = run_state.summary
        if s.errored or s.skipped:
            label = f"❌ finished with {s.errored} error(s)"
            if s.skipped:
                label += f", {s.skipped} skipped"
            return Text(label, style="bold red")
        return Text("✅ completed successfully", style="bold green")

    def _with_mascot(self, content: Group, run_state: RunState) -> Table:
        """Float the mascot in the top-right corner without it taking its own
        lines. A two-column grid puts the content on the left (filling the width)
        and a fixed-width left-justified "track" cell on the right; the dino's own
        leading pad walks it across that cell. A right-justified cell would
        collapse the pad and kill the movement."""
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(justify="left", width=MASCOT_CELL_WIDTH)
        mood = MascotMood.from_run(run_state)
        grid.add_row(content, self._mascot.frame(mood))
        return grid

    def _section_size(self, run_state: RunState) -> int:
        threads = run_state.summary.threads
        return threads if threads else self.up_next

    def _bar(self, run_state: RunState) -> Text:
        total = run_state.run_total
        done = run_state.done
        ratio = done / total if total else 0.0
        filled = int(ratio * BAR_WIDTH)
        pct = int(ratio * 100)
        bar = Text()
        bar.append(FILLED_BLOCK * filled, style="bold cyan")
        bar.append(EMPTY_BLOCK * (BAR_WIDTH - filled), style="grey37")
        bar.append(f" {pct:>3}%", style="bold cyan")
        bar.append(f"  {done}/{total} models", style="bold white")
        return bar

    def _tally(self, run_state: RunState) -> Text:
        s = run_state.summary
        line = Text()
        if s.threads is not None and s.target is not None:
            line.append(f"{s.target} ", style="bold magenta")
            line.append(f"| {s.threads} threads — ", style="grey50")
        line.append(f"PASS={s.passed} ", style="bold green")
        line.append(f"WARN={s.warned} ", style="bold yellow")
        line.append(f"ERROR={s.errored} ", style="bold red")
        line.append(f"SKIP={s.skipped}", style="grey50")
        return line

    def _running_row(self, model: ModelRun) -> Text:
        detail = f"{model.elapsed:.1f}s" if model.elapsed is not None else "in progress"
        line = Text()
        line.append(f"  {RUNNING_GLYPH} ", style=RUNNING_STYLE)
        line.append(f"{_truncate(model.name):<{NAME_WIDTH}}", style="bold white")
        line.append(detail, style="grey62")
        return line

    def _upcoming_row(self, run_state: RunState, model: ModelRun) -> Text:
        line = Text()
        line.append(f"  {QUEUED_GLYPH} ", style=QUEUED_STYLE)
        line.append(f"{_truncate(model.name):<{NAME_WIDTH}}", style="grey78")
        line.append(self._detail(run_state, model), style="grey50")
        return line

    def _detail(self, run_state: RunState, model: ModelRun) -> str:
        blockers = run_state.waiting_on(model.unique_id)
        return f"waiting on {', '.join(blockers)}" if blockers else "queued"


def _truncate(name: str) -> str:
    return name if len(name) <= NAME_WIDTH - 1 else name[: NAME_WIDTH - 2] + "…"
