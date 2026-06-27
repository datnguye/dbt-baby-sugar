"""Read dbt's manifest.json once to seed the run model with the DAG."""

from __future__ import annotations

import json
from pathlib import Path

from dbt_baby_sugar.core.model_run import ModelRun
from dbt_baby_sugar.core.run_state import RunState

DEFAULT_TARGET_DIR = "target"
MANIFEST_NAME = "manifest.json"
RUNNABLE_RESOURCE_TYPES = frozenset({"model", "seed", "snapshot"})


class ManifestReader:
    def __init__(self, target_dir: str | Path = DEFAULT_TARGET_DIR) -> None:
        self.manifest_path = Path(target_dir) / MANIFEST_NAME

    def exists(self) -> bool:
        return self.manifest_path.is_file()

    def read_models(self) -> list[ModelRun]:
        """Parse the runnable nodes (model/seed/snapshot) and their DAG edges.

        Returns an empty list rather than raising if the manifest is absent or
        unreadable — a half-written file mid-parse is expected on a cold first
        run, and a failed enrichment should never sink the run.
        """
        try:
            raw = json.loads(self.manifest_path.read_text())
        except (OSError, ValueError):
            return []
        nodes = raw.get("nodes", {})
        models = []
        for unique_id, node in nodes.items():
            if node.get("resource_type") not in RUNNABLE_RESOURCE_TYPES:
                continue
            depends_on = node.get("depends_on", {}).get("nodes", [])
            models.append(
                ModelRun(
                    unique_id=unique_id,
                    name=node.get("name", unique_id),
                    depends_on=frozenset(depends_on),
                )
            )
        return models

    def load(self) -> RunState:
        return RunState(self.read_models())
