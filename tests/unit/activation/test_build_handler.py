from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

import dbt_baby_sugar.activation.activation as activation_mod
from dbt_baby_sugar.events.event_handler import SugarEventHandler


@pytest.fixture(autouse=True)
def silent_app(monkeypatch):
    # Don't touch stdout or launch a real Textual thread while building handlers.
    monkeypatch.setattr(
        activation_mod,
        "install_capture",
        lambda sink: types.SimpleNamespace(original=sys.stdout),
    )
    monkeypatch.setattr(activation_mod.SugarAppDriver, "start", lambda self: None)


def test_build_handler_reads_manifest(monkeypatch, manifest_dir: Path):
    monkeypatch.chdir(manifest_dir.parent)
    handler = activation_mod._build_handler()
    assert isinstance(handler, SugarEventHandler)
    assert handler.run_state.waiting_on("model.p.fct_orders") == ["stg_orders"]
    # Already seeded, so no mid-run reload is armed.
    assert handler._dag_pending is False


def test_build_handler_without_manifest(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    handler = activation_mod._build_handler()
    assert handler.run_state.total == 0
    # Cold start: a reader is armed so the DAG can be grafted on mid-run.
    assert handler._dag_pending is True


def test_build_handler_wires_driver_as_renderer(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    handler = activation_mod._build_handler()
    assert isinstance(handler.renderer, activation_mod.SugarAppDriver)
