"""A Yes/No modal asking whether to cancel the dbt run.

Pushed when the user hits Ctrl+C. It dismisses with ``True`` (cancel the run and
quit) or ``False`` (keep running) so the caller decides what to do — the screen
itself stays ignorant of how cancellation is wired into dbt's main thread.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmCancelScreen(ModalScreen[bool]):
    CSS = """
    ConfirmCancelScreen {
        align: center middle;
    }
    #dialog {
        grid-size: 2 2;        /* 2 columns; row 1 is the question, row 2 the buttons */
        grid-rows: 3 5;        /* question gets 3 cells; the button row gets 5 — 2 of
                                  vertical slack so a 3-cell button never reaches the
                                  border, even if the real driver's height math drifts */
        grid-gutter: 1 2;
        padding: 1 2;
        width: 64;
        height: 16;            /* generously taller than the content needs, so the
                                  buttons can't overflow the frame on any driver */
        border: thick $error;
        background: $surface;
    }
    #question {
        column-span: 2;
        content-align: center middle;
        text-align: center;
    }
    #dialog Button {
        width: 100%;
        height: 3;             /* pin the button height so it never grows into the border */
    }
    """

    BINDINGS = [("escape", "keep", "Keep running")]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Cancel the dbt run and quit?", id="question"),
            Button("Yes, cancel", variant="error", id="yes"),
            Button("No, keep running", variant="primary", id="no"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_keep(self) -> None:
        self.dismiss(False)
