"""Shared UI-test helper: render a Rich renderable to plain text for assertions."""

from __future__ import annotations

from rich.console import Console, RenderableType


def render_text(renderable: RenderableType, width: int = 100) -> str:
    """Capture a Rich renderable as plain (non-terminal) text the way the UI tests
    assert against it. Width defaults to 100; the mascot tests pass 60."""
    console = Console(width=width, force_terminal=False)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()
