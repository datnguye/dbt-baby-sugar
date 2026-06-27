"""Intercept dbt's stdout so its log lines flow into the log pane, not the screen.

dbt binds a ``StreamHandler`` to ``sys.stdout`` eagerly, so capturing reliably
means two things: become ``sys.stdout`` for anything that resolves it lazily,
and retarget any handler already bound to the previous stream. Captured text is
split into lines and pushed to a ``LogSink`` (the app driver); nothing reaches
the terminal, because Textual owns the screen.
"""

from __future__ import annotations

import logging
import sys
from typing import Protocol, TextIO


class LogSink(Protocol):
    def append(self, line: str) -> None: ...


class StdoutCapture:
    def __init__(self, sink: LogSink, original: TextIO) -> None:
        self.sink = sink
        self.original = original
        self._partial = ""

    def write(self, text: str) -> int:
        self._partial += text
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            self.sink.append(line)
        return len(text)

    def flush(self) -> None:
        if self._partial:
            self.sink.append(self._partial)
            self._partial = ""

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return self.original.fileno()


def install_capture(sink: LogSink) -> StdoutCapture:
    capture = StdoutCapture(sink, sys.stdout)
    sys.stdout = capture
    _retarget_stream_handlers(capture.original, capture)
    return capture


def _retarget_stream_handlers(old: TextIO, new: StdoutCapture) -> None:
    for logger in _all_loggers():
        for handler in getattr(logger, "handlers", ()):
            if isinstance(handler, logging.StreamHandler) and handler.stream is old:
                handler.setStream(new)


def _all_loggers() -> list[logging.Logger]:
    manager_dict = logging.Logger.manager.loggerDict.values()
    loggers = [logging.getLogger()]
    loggers += [lg for lg in manager_dict if isinstance(lg, logging.Logger)]
    return loggers
