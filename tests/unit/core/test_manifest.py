from __future__ import annotations

from pathlib import Path

from dbt_baby_sugar.core.manifest import ManifestReader


def test_load_seeds_dag_but_nodes_start_unseen(manifest_dir: Path) -> None:
    reader = ManifestReader(manifest_dir)
    assert reader.exists()
    state = reader.load()
    assert state.total == 0
    assert state.waiting_on("model.p.fct_orders") == ["stg_orders"]
    state.start("model.p.fct_orders")
    assert state.total == 1


def test_exists_false_when_missing(tmp_path: Path) -> None:
    reader = ManifestReader(tmp_path)
    assert not reader.exists()


def test_read_models_returns_empty_when_missing(tmp_path: Path) -> None:
    # A cold first run reads before dbt has written the manifest — no crash.
    reader = ManifestReader(tmp_path)
    assert reader.read_models() == []


def test_read_models_returns_empty_on_half_written_manifest(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text("{ not valid json")
    reader = ManifestReader(tmp_path)
    assert reader.read_models() == []
