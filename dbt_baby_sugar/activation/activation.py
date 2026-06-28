"""Attach dbt-sugar to dbt's event bus, idempotently.

Primary path (dbt 1.8+): register a callback on the global EventManager.
Fallback: monkey-patch EventManager.fire_event for environments where the
callback registry is not reachable.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

from dbt_baby_sugar.core.manifest import ManifestReader
from dbt_baby_sugar.core.run_state import RunState
from dbt_baby_sugar.events.event_handler import SugarEventHandler
from dbt_baby_sugar.ui.app.app_driver import SugarAppDriver
from dbt_baby_sugar.ui.capture.stdout_capture import install_capture

_INSTALLED = False


def _running_under_dbt() -> bool:
    return "dbt" in sys.modules or any("dbt" in arg for arg in sys.argv[:1])


def _build_handler() -> SugarEventHandler:
    reader = ManifestReader()
    seeded = reader.exists()
    run_state = reader.load() if seeded else RunState()
    driver = SugarAppDriver()
    install_capture(driver)
    # NB: do not start the app here — it starts lazily on the first event, after
    # dbt's spawn-based adapter setup is done (see SugarAppDriver for why).
    #
    # On a cold first run the manifest does not exist yet, so hand the reader to
    # the handler: dbt writes manifest.json during parse and the handler grafts
    # the DAG on at the first node event, keeping "up next" alive (see
    # SugarEventHandler._maybe_seed_dag). When already seeded, no reload is needed.
    lazy_reader = None if seeded else reader
    return SugarEventHandler(run_state, driver, manifest_reader=lazy_reader)


def _optional_import(name: str) -> Any | None:
    """Import a dbt-internal module, or None if it isn't importable here.

    The two install paths each reach into a different ``dbt_common`` module that
    may be absent depending on the dbt version, so both guard the import the same
    way; this folds that shared try/except into one place.
    """
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def _install_via_callback(handler: SugarEventHandler) -> bool:
    functions = _optional_import("dbt_common.events.functions")
    if functions is None:
        return False
    functions.get_event_manager().add_callback(handler)
    return True


def _make_patched(original, handler):
    def patched(self, e, *args, **kwargs):
        original(self, e, *args, **kwargs)
        handler(e)

    return patched


def _install_via_patch(handler: SugarEventHandler) -> bool:
    event_manager = _optional_import("dbt_common.events.event_manager")
    if event_manager is None:
        return False
    manager_cls = event_manager.EventManager
    manager_cls.fire_event = _make_patched(manager_cls.fire_event, handler)
    return True


def install() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return True
    handler = _build_handler()
    if _install_via_callback(handler) or _install_via_patch(handler):
        _INSTALLED = True
    return _INSTALLED


def activate() -> bool:
    if not _running_under_dbt():
        return False
    return install()
