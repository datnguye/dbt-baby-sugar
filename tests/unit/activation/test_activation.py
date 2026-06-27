from __future__ import annotations

import sys
import types

import pytest

import dbt_baby_sugar.activation.activation as activation_mod
from dbt_baby_sugar.activation.activation import install
from dbt_baby_sugar.events.event_handler import SugarEventHandler


@pytest.fixture(autouse=True)
def reset_install_guard(monkeypatch):
    monkeypatch.setattr(activation_mod, "_INSTALLED", False)


@pytest.fixture
def quiet_handler(monkeypatch):
    handler = SugarEventHandler.__new__(SugarEventHandler)
    monkeypatch.setattr(activation_mod, "_build_handler", lambda: handler)
    return handler


def _fake_module(monkeypatch, name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _block_import(monkeypatch, name: str):
    monkeypatch.setitem(sys.modules, name, None)


def test_install_via_callback(monkeypatch, quiet_handler):
    registered = []

    class Manager:
        loggers = []

        def add_callback(self, cb):
            registered.append(cb)

    _fake_module(monkeypatch, "dbt_common.events.functions", get_event_manager=lambda: Manager())

    assert install() is True
    assert registered == [quiet_handler]


def test_install_is_idempotent(monkeypatch, quiet_handler):
    calls = []
    _fake_module(
        monkeypatch,
        "dbt_common.events.functions",
        get_event_manager=lambda: types.SimpleNamespace(add_callback=calls.append, loggers=[]),
    )

    assert install() is True
    assert install() is True
    assert len(calls) == 1


def test_install_falls_back_to_patch(monkeypatch):
    _block_import(monkeypatch, "dbt_common.events.functions")

    fired = []
    handled = []

    class EventManager:
        def fire_event(self, e, *args, **kwargs):
            fired.append(("orig", e))

    _fake_module(monkeypatch, "dbt_common.events.event_manager", EventManager=EventManager)

    def fake_handler(e):
        handled.append(e)

    monkeypatch.setattr(activation_mod, "_build_handler", lambda: fake_handler)

    assert install() is True
    EventManager().fire_event("evt")
    assert ("orig", "evt") in fired
    assert handled == ["evt"]


def test_install_returns_false_when_unavailable(monkeypatch, quiet_handler):
    _block_import(monkeypatch, "dbt_common.events.functions")
    _block_import(monkeypatch, "dbt_common.events.event_manager")

    assert install() is False


def test_activate_skips_when_not_under_dbt(monkeypatch):
    monkeypatch.setattr(activation_mod, "_running_under_dbt", lambda: False)
    monkeypatch.setattr(activation_mod, "install", lambda: pytest.fail("install should not run"))
    assert activation_mod.activate() is False


def test_activate_installs_when_under_dbt(monkeypatch):
    monkeypatch.setattr(activation_mod, "_running_under_dbt", lambda: True)
    monkeypatch.setattr(activation_mod, "install", lambda: True)
    assert activation_mod.activate() is True


def test_running_under_dbt_detects_sys_modules(monkeypatch):
    monkeypatch.setitem(sys.modules, "dbt", types.ModuleType("dbt"))
    monkeypatch.setattr(sys, "argv", ["pytest"])
    assert activation_mod._running_under_dbt() is True


def test_running_under_dbt_detects_argv(monkeypatch):
    monkeypatch.delitem(sys.modules, "dbt", raising=False)
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/dbt", "run"])
    assert activation_mod._running_under_dbt() is True


def test_running_under_dbt_false_when_absent(monkeypatch):
    monkeypatch.delitem(sys.modules, "dbt", raising=False)
    monkeypatch.setattr(sys, "argv", ["pytest", "-q"])
    assert activation_mod._running_under_dbt() is False
