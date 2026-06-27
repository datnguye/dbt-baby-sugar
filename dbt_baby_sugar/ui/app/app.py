"""The Textual UI: a fixed overview panel above a mouse-scrollable dbt log.

Textual owns the screen and the event loop, so borders are framework-managed
(no manual clipping or drift) and the log pane scrolls with the mouse wheel —
no keyboard bindings needed. ``RichLog`` keeps the whole run's log
(``max_lines=None``) and follows the tail while still letting you wheel back to
earlier lines (``auto_scroll=True``).

dbt owns the main thread, so this app runs on a background thread (see
``SugarAppDriver``) and is updated through ``call_from_thread`` — hence the two
thread-safe entry points ``set_overview`` and ``write_log``.
"""

from __future__ import annotations

import os
import signal

from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.driver import Driver
from textual.drivers.linux_driver import LinuxDriver
from textual.widgets import RichLog, Static

from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.ui.app.confirm_cancel import ConfirmCancelScreen
from dbt_baby_sugar.ui.app.threadsafe_driver import ThreadSafeLinuxDriver
from dbt_baby_sugar.ui.overview.overview import OverviewFormatter

RUNNING_HINT = "scroll the log with your mouse · Ctrl+C to cancel"
DONE_HINT = "✅ dbt finished — press Enter (or q) to close"
# Repaint cadence for the mascot. The overview re-renders on this timer, NOT on
# dbt events, so the dino keeps animating even during a long silent compile.
REFRESH_INTERVAL = 0.2


class SugarApp(App[None]):
    CSS = """
    #overview {
        height: auto;          /* shrink to content — no dead space once finished */
        max-height: 14;        /* but cap a wide run (many threads) and scroll it */
        border: round $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    #log {
        height: 1fr;           /* the log takes the rest of the screen */
        border: round $accent;
        padding: 0 1;
    }
    #hint {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    #hint.done {
        color: $success;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("enter", "quit", "Close"),
        ("q", "quit", "Close"),
        # Priority so it beats Textual's built-in ctrl+c quit: we want a confirm.
        Binding("ctrl+c", "request_cancel", "Cancel run", priority=True),
    ]

    overview_content: RenderableType = "(waiting for dbt…)"

    def __init__(self) -> None:
        super().__init__()
        self._formatter = OverviewFormatter()
        self._run_state: RunState | None = None

    def on_mount(self) -> None:
        """Repaint the overview on a timer, not on dbt events, so the mascot keeps
        animating through long silent stretches (e.g. dbt parse/compile)."""
        self.set_interval(REFRESH_INTERVAL, self._tick)

    def _tick(self) -> None:
        if self._run_state is not None:
            self._render_overview(self._run_state)

    def action_request_cancel(self) -> None:
        self.push_screen(ConfirmCancelScreen(), self._on_cancel_choice)

    def _on_cancel_choice(self, cancel: bool | None) -> None:
        """On "Yes", SIGINT ourselves so dbt (on the main thread) cancels the run
        the way Ctrl+C normally would, then tear the UI down. On "No"/dismiss,
        let dbt keep running."""
        if not cancel:
            return
        os.kill(os.getpid(), signal.SIGINT)
        self.exit()

    def get_driver_class(self) -> type[Driver]:
        """Swap the POSIX driver for one that won't crash registering signal
        handlers off-main (we run on a daemon thread; dbt owns the main thread).
        The headless test driver and the Windows driver are left untouched."""
        driver = super().get_driver_class()
        return ThreadSafeLinuxDriver if driver is LinuxDriver else driver

    def compose(self) -> ComposeResult:
        overview = Static(self.overview_content, id="overview")
        overview.border_title = "overview"
        log = RichLog(id="log", max_lines=None, wrap=False, auto_scroll=True)
        log.border_title = "dbt log"
        yield overview
        yield log
        yield Static(RUNNING_HINT, id="hint")

    def mark_done(self) -> None:
        """Switch the footer to the dismiss prompt and keep the app up so the user
        can read/scroll the final log until they press Enter."""
        hint = self.query_one("#hint", Static)
        hint.update(DONE_HINT)
        hint.add_class("done")

    def set_run_state(self, run_state: RunState) -> None:
        """Store the latest dbt snapshot. The repaint timer — not this call — is the
        sole animator, so the mascot advances at one steady cadence regardless of
        how dbt's events or log lines burst. New snapshot data appears on the next
        tick (a fraction of a second later)."""
        self._run_state = run_state

    def _render_overview(self, run_state: RunState) -> None:
        renderable = self._formatter.render(run_state)
        self.overview_content = renderable
        self.query_one("#overview", Static).update(renderable)

    def write_log(self, line: str) -> None:
        self.query_one("#log", RichLog).write(line)
