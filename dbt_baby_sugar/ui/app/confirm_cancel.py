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
        /* Paint the whole screen opaque so the native dbt log underneath can't
           bleed through around the dialog (it was showing on every row before). */
        background: $background;
    }
    #dialog {
        grid-size: 2 2;        /* 2 columns; row 1 is the question, row 2 the buttons */
        grid-rows: 1fr 3;      /* question takes the slack; buttons get exactly 3 cells */
        grid-gutter: 1 2;
        padding: 1 2;
        width: 60;
        height: 11;            /* compact enough to fit a short terminal, with the bottom
                                  border on-screen: border(2)+padding(2)+1fr+gutter(1)+buttons(3) */
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
