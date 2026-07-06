import json
from pathlib import Path

import pytest

from app.adapters.dbt_manifest_adapter import DbtManifestAdapter


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_manifest(tmp_path: Path, data: dict) -> str:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _model(
    name: str,
    schema: str = "staging",
    alias: str | None = None,
    materialized: str = "table",
    enabled: bool = True,
    depends_on: list[str] | None = None,
    compiled_code: str | None = "SELECT 1",
    description: str = "",
    package: str = "proj",
    **extra,
) -> dict:
    node = {
        "resource_type": "model",
        "package_name": package,
        "name": name,
        "schema": schema,
        "alias": alias,
        "description": description,
        "config": {"materialized": materialized, "enabled": enabled},
        "depends_on": {"nodes": depends_on or []},
    }
    if compiled_code is not None:
        node["compiled_code"] = compiled_code
    node.update(extra)
    return node


def _source(name: str, schema: str = "raw", identifier: str | None = None) -> dict:
    return {
        "resource_type": "source",
        "name": name,
        "schema": schema,
        "identifier": identifier or name,
    }


def _unique_test(model_id: str, column: str) -> dict:
    return {
        "resource_type": "test",
        "name": f"unique_{column}",
        "column_name": column,
        "test_metadata": {"name": "unique", "kwargs": {"column_name": column}},
        "depends_on": {"nodes": [model_id]},
    }


# ── mapping ───────────────────────────────────────────────────────────────────

def test_model_maps_to_pipeline_job(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.stg_orders": _model(
                "stg_orders", schema="staging", alias="orders",
                depends_on=["source.proj.raw.orders"],
                compiled_code="SELECT * FROM raw.orders",
                description="Load orders\nMore detail here.",
            ),
        },
        "sources": {"source.proj.raw.orders": _source("orders")},
    })
    jobs = DbtManifestAdapter(path).load()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.config_key == "stg_orders"
    assert job.pipeline_name == "Load orders"  # first line of the description
    assert job.enabled is True
    assert job.source_table == "raw.orders"
    assert job.target_table == "staging.orders"
    assert job.sql_query == "SELECT * FROM raw.orders"
    assert job.load_type == "full"  # table → full
    assert job.depends_on == ["raw.orders"]


def test_multi_parent_model_keeps_all_dependencies(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.a": _model("a", depends_on=["source.proj.raw.x"]),
            "model.proj.b": _model("b", depends_on=["source.proj.raw.y"]),
            "model.proj.joined": _model(
                "joined", schema="mart",
                depends_on=["model.proj.a", "model.proj.b"],
            ),
        },
        "sources": {
            "source.proj.raw.x": _source("x"),
            "source.proj.raw.y": _source("y"),
        },
    })
    jobs = {j.config_key: j for j in DbtManifestAdapter(path).load()}
    joined = jobs["joined"]
    assert joined.source_table == "staging.a"  # first parent is primary
    assert joined.depends_on == ["staging.a", "staging.b"]


def test_load_type_mapping(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.t": _model("t", materialized="table", depends_on=["source.proj.raw.x"]),
            "model.proj.i": _model("i", materialized="incremental", depends_on=["source.proj.raw.x"]),
            "model.proj.v": _model("v", materialized="view", depends_on=["source.proj.raw.x"]),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    jobs = {j.config_key: j for j in DbtManifestAdapter(path).load()}
    assert jobs["t"].load_type == "full"
    assert jobs["i"].load_type == "incremental"
    assert jobs["v"].load_type == "view"


def test_disabled_model_is_marked_disabled(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.off": _model("off", enabled=False, depends_on=["source.proj.raw.x"]),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    jobs = DbtManifestAdapter(path).load()
    assert jobs[0].enabled is False


def test_primary_key_derived_from_unique_test(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.m": _model("m", depends_on=["source.proj.raw.x"]),
            "test.proj.unique_m_id": _unique_test("model.proj.m", "order_id"),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    assert DbtManifestAdapter(path).load()[0].primary_key == "order_id"


def test_no_unique_test_means_no_primary_key(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {"model.proj.m": _model("m", depends_on=["source.proj.raw.x"])},
        "sources": {"source.proj.raw.x": _source("x")},
    })
    assert DbtManifestAdapter(path).load()[0].primary_key is None


def test_ephemeral_model_resolved_through_not_emitted(tmp_path):
    # final depends on an ephemeral model, which depends on a source. The
    # ephemeral is not a job; final's lineage looks through it to the source.
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.eph": _model(
                "eph", materialized="ephemeral", depends_on=["source.proj.raw.x"],
            ),
            "model.proj.final": _model("final", depends_on=["model.proj.eph"]),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    jobs = DbtManifestAdapter(path).load()
    assert [j.config_key for j in jobs] == ["final"]
    assert jobs[0].source_table == "raw.x"


def test_model_without_parents_is_skipped(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj.spine": _model("spine", depends_on=[]),
            "model.proj.real": _model("real", depends_on=["source.proj.raw.x"]),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    assert [j.config_key for j in DbtManifestAdapter(path).load()] == ["real"]


def test_raw_code_fallback_when_not_compiled(tmp_path):
    node = _model("m", depends_on=["source.proj.raw.x"], compiled_code=None)
    node["raw_code"] = "SELECT * FROM {{ source('raw', 'x') }}"
    path = _write_manifest(tmp_path, {
        "nodes": {"model.proj.m": node},
        "sources": {"source.proj.raw.x": _source("x")},
    })
    assert DbtManifestAdapter(path).load()[0].sql_query == "SELECT * FROM {{ source('raw', 'x') }}"


def test_name_collision_qualified_with_package(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {
            "model.proj_a.m": _model("m", package="proj_a", depends_on=["source.proj.raw.x"]),
            "model.proj_b.m": _model("m", package="proj_b", depends_on=["source.proj.raw.x"]),
        },
        "sources": {"source.proj.raw.x": _source("x")},
    })
    keys = [j.config_key for j in DbtManifestAdapter(path).load()]
    assert keys == ["m", "proj_b.m"]


def test_source_identifier_preferred_over_name(tmp_path):
    path = _write_manifest(tmp_path, {
        "nodes": {"model.proj.m": _model("m", depends_on=["source.proj.raw.x"])},
        "sources": {"source.proj.raw.x": _source("x", identifier="x_landing")},
    })
    assert DbtManifestAdapter(path).load()[0].source_table == "raw.x_landing"


# ── errors ────────────────────────────────────────────────────────────────────

def test_missing_manifest_raises():
    with pytest.raises(FileNotFoundError):
        DbtManifestAdapter("/nonexistent/manifest.json").load()


def test_invalid_json_raises_value_error(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        DbtManifestAdapter(str(path)).load()


def test_missing_nodes_raises_value_error(tmp_path):
    path = _write_manifest(tmp_path, {"metadata": {}})
    with pytest.raises(ValueError, match="missing the 'nodes'"):
        DbtManifestAdapter(str(Path(path))).load()


# ── shipped sample ────────────────────────────────────────────────────────────

_SAMPLE = Path(__file__).parent.parent.parent / "samples" / "dbt_manifest_sample.json"


def test_shipped_sample_manifest_loads():
    jobs = {j.config_key: j for j in DbtManifestAdapter(str(_SAMPLE)).load()}
    assert set(jobs) == {"stg_orders", "stg_customers", "orders_enriched"}
    assert jobs["stg_orders"].target_table == "staging.orders"
    assert jobs["stg_orders"].primary_key == "order_id"  # from the unique test
    assert jobs["orders_enriched"].depends_on == ["staging.orders", "staging.customers"]
    assert jobs["orders_enriched"].load_type == "full"
