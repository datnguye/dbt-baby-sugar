from __future__ import annotations

import io
import logging
import sys

import pytest

from dbt_baby_sugar.ui.capture.stdout_capture import StdoutCapture, install_capture


class ListSink:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def append(self, line: str) -> None:
        self.lines.append(line)


@pytest.fixture
def sink() -> ListSink:
    return ListSink()


def test_write_splits_on_newlines(sink: ListSink) -> None:
    capture = StdoutCapture(sink, io.StringIO())
    n = capture.write("alpha\nbeta\n")
    assert n == len("alpha\nbeta\n")
    assert sink.lines == ["alpha", "beta"]


def test_write_buffers_partial_until_flush(sink: ListSink) -> None:
    capture = StdoutCapture(sink, io.StringIO())
    capture.write("partial")
    assert sink.lines == []
    capture.flush()
    assert sink.lines == ["partial"]


def test_flush_without_partial_is_noop(sink: ListSink) -> None:
    capture = StdoutCapture(sink, io.StringIO())
    capture.flush()
    assert sink.lines == []


def test_isatty_and_fileno_delegate(sink: ListSink) -> None:
    class FakeStream:
        def fileno(self) -> int:
            return 7

    capture = StdoutCapture(sink, FakeStream())
    assert capture.isatty() is False
    assert capture.fileno() == 7


def test_install_capture_replaces_stdout_and_retargets(sink: ListSink, monkeypatch) -> None:
    original = io.StringIO()
    monkeypatch.setattr(sys, "stdout", original)

    logger = logging.getLogger("dbt_baby_sugar.test.capture")
    handler = logging.StreamHandler(original)
    logger.addHandler(handler)
    try:
        capture = install_capture(sink)
        assert sys.stdout is capture
        assert handler.stream is capture
        print("hello")
        assert sink.lines == ["hello"]
    finally:
        logger.removeHandler(handler)
