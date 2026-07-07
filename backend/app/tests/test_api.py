from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE = "sample_config.csv"
CYCLE = "cycle_config.csv"
BAD = "bad_schema.csv"


# --- /pipelines ---

def test_list_pipelines():
    r = client.get("/pipelines/", params={"file": SAMPLE})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 7
    keys = [j["config_key"] for j in data]
    assert "etl_001" in keys


def test_get_pipeline_by_key():
    r = client.get("/pipelines/etl_003", params={"file": SAMPLE})
    assert r.status_code == 200
    assert r.json()["config_key"] == "etl_003"
    assert r.json()["target_table"] == "mart.orders"


def test_get_pipeline_not_found():
    r = client.get("/pipelines/nonexistent", params={"file": SAMPLE})
    assert r.status_code == 404


def test_list_pipelines_file_not_found():
    r = client.get("/pipelines/", params={"file": "does_not_exist.csv"})
    assert r.status_code == 404


def test_list_pipelines_bad_csv():
    r = client.get("/pipelines/", params={"file": BAD})
    assert r.status_code == 422


def test_path_traversal_returns_400():
    r = client.get("/pipelines/", params={"file": "../sample_config.csv"})
    assert r.status_code == 400


# --- /graph ---

def test_get_graph():
    r = client.get("/graph/", params={"file": SAMPLE})
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["execution_order"], list)
    assert data["cycle_detected"] is False


def test_get_graph_with_cycle():
    r = client.get("/graph/", params={"file": CYCLE})
    assert r.status_code == 200
    data = r.json()
    assert data["cycle_detected"] is True
    assert data["execution_order"] is None


# --- /findings ---

def test_get_findings():
    r = client.get("/findings/", params={"file": SAMPLE})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    types = {f["finding_type"] for f in data}
    assert "duplicate_target" in types
    assert "disabled_dependency" in types


def test_get_findings_severity_values():
    r = client.get("/findings/", params={"file": SAMPLE})
    severities = {f["severity"] for f in r.json()}
    assert severities <= {"error", "warning", "info"}


_RECONCILIATION_TYPES = {
    "empty_target",
    "row_count_drop",
    "null_primary_key",
    "duplicate_primary_key",
}


def test_get_findings_without_data_dir_excludes_reconciliation():
    # Regression: omitting data_dir keeps the structural + SQL behavior unchanged.
    r = client.get("/findings/", params={"file": "demo_config.csv"})
    assert r.status_code == 200
    types = {f["finding_type"] for f in r.json()}
    assert types.isdisjoint(_RECONCILIATION_TYPES)


def test_get_findings_with_data_dir_includes_reconciliation():
    r = client.get("/findings/", params={"file": "demo_config.csv", "data_dir": "."})
    assert r.status_code == 200
    types = {f["finding_type"] for f in r.json()}
    assert "row_count_drop" in types
    assert "duplicate_primary_key" in types
    # Structural/SQL findings are still present alongside reconciliation findings.
    assert "select_star" in types


def test_get_findings_data_dir_path_traversal():
    r = client.get("/findings/", params={"file": "demo_config.csv", "data_dir": "../samples"})
    assert r.status_code == 400


def test_get_findings_data_dir_not_found():
    r = client.get("/findings/", params={"file": "demo_config.csv", "data_dir": "nope"})
    assert r.status_code == 404


# --- /statistics ---

DEMO = "demo_config.csv"


def test_get_statistics_returns_list():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "."})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # 3 enabled jobs in the demo config (etl_004 is disabled and excluded)
    keys = [s["config_key"] for s in data]
    assert keys == ["etl_001", "etl_002", "etl_003"]


def test_get_statistics_fields_present():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "."})
    first = r.json()[0]
    for field in (
        "config_key", "pipeline_name", "source_table", "target_table",
        "source_count", "target_count", "lost_rows", "loss_pct",
        "target_empty", "primary_key",
        "primary_key_null_count", "primary_key_null_pct", "primary_key_duplicate_count",
    ):
        assert field in first


def test_get_statistics_numeric_correctness():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "."})
    by_key = {s["config_key"]: s for s in r.json()}
    # raw.orders has 20 rows, staging.orders has 18 → 2 lost (10.0%)
    orders = by_key["etl_001"]
    assert orders["source_count"] == 20
    assert orders["target_count"] == 18
    assert orders["lost_rows"] == 2
    assert orders["loss_pct"] == 10.0
    assert orders["target_empty"] is False


def test_get_statistics_missing_target_table_yields_none():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "."})
    by_key = {s["config_key"]: s for s in r.json()}
    # etl_003 targets mart.orders_enriched, which has no file in demo_data
    enrich = by_key["etl_003"]
    assert enrich["target_count"] is None
    assert enrich["lost_rows"] is None
    assert enrich["primary_key_null_count"] is None


def test_get_statistics_excludes_disabled():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "."})
    keys = [s["config_key"] for s in r.json()]
    assert "etl_004" not in keys


def test_get_statistics_default_data_dir():
    # data_dir defaults to "." (the data root) when omitted
    r = client.get("/statistics/", params={"file": DEMO})
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_get_statistics_config_not_found():
    r = client.get("/statistics/", params={"file": "does_not_exist.csv", "data_dir": "."})
    assert r.status_code == 404


def test_get_statistics_config_bad_schema():
    r = client.get("/statistics/", params={"file": BAD, "data_dir": "."})
    assert r.status_code == 422


def test_get_statistics_config_path_traversal():
    r = client.get("/statistics/", params={"file": "../sample_config.csv", "data_dir": "."})
    assert r.status_code == 400


def test_get_statistics_data_dir_path_traversal():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "../samples"})
    assert r.status_code == 400


def test_get_statistics_data_dir_not_found():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": "nonexistent_subdir"})
    assert r.status_code == 404


# --- /profile ---

def test_get_profile_returns_profile_and_findings():
    r = client.get("/profile/", params={"table": "staging.orders", "data_dir": "."})
    assert r.status_code == 200
    data = r.json()
    assert "profile" in data
    assert "findings" in data
    profile = data["profile"]
    assert profile["table_name"] == "staging.orders"
    assert profile["row_count"] == 18
    assert profile["column_count"] == 5
    columns = {c["column_name"] for c in profile["columns"]}
    assert "coupon_code" in columns


def test_get_profile_reports_high_null_rate():
    r = client.get("/profile/", params={"table": "staging.orders", "data_dir": "."})
    # coupon_code is ~83% null in the demo data → high_null_rate warning
    types = {f["finding_type"] for f in r.json()["findings"]}
    assert "high_null_rate" in types


def test_get_profile_table_not_found():
    r = client.get("/profile/", params={"table": "staging.missing", "data_dir": "."})
    assert r.status_code == 404


def test_get_profile_invalid_table_name():
    r = client.get("/profile/", params={"table": "../etc", "data_dir": "."})
    assert r.status_code == 400


def test_get_profile_data_dir_path_traversal():
    r = client.get("/profile/", params={"table": "staging.orders", "data_dir": "../samples"})
    assert r.status_code == 400


def test_get_profile_data_dir_not_found():
    r = client.get("/profile/", params={"table": "staging.orders", "data_dir": "nope"})
    assert r.status_code == 404


# --- dbt manifest source (manifest=) ---

MANIFEST = "dbt_manifest_sample.json"


def test_list_pipelines_from_manifest():
    r = client.get("/pipelines/", params={"manifest": MANIFEST})
    assert r.status_code == 200
    jobs = {j["config_key"]: j for j in r.json()}
    assert set(jobs) == {"stg_orders", "stg_customers", "orders_enriched"}
    assert jobs["stg_orders"]["target_table"] == "staging.orders"
    assert jobs["stg_orders"]["primary_key"] == "order_id"  # from the unique test
    assert jobs["orders_enriched"]["depends_on"] == ["staging.orders", "staging.customers"]


def test_graph_from_manifest_has_multi_parent_edges():
    r = client.get("/graph/", params={"manifest": MANIFEST})
    assert r.status_code == 200
    data = r.json()
    edges = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("staging.orders", "mart.orders_enriched") in edges
    assert ("staging.customers", "mart.orders_enriched") in edges
    assert data["cycle_detected"] is False


def test_findings_from_manifest_with_reconciliation():
    r = client.get("/findings/", params={"manifest": MANIFEST, "data_dir": "."})
    assert r.status_code == 200
    types = {f["finding_type"] for f in r.json()}
    assert "select_star" in types              # stg_orders compiled SQL
    assert "duplicate_primary_key" in types    # staging.customers dup customer_id


def test_statistics_from_manifest():
    r = client.get("/statistics/", params={"manifest": MANIFEST, "data_dir": "."})
    assert r.status_code == 200
    keys = [s["config_key"] for s in r.json()]
    assert "stg_orders" in keys


def test_file_and_manifest_together_rejected():
    r = client.get("/pipelines/", params={"file": SAMPLE, "manifest": MANIFEST})
    assert r.status_code == 400


def test_neither_file_nor_manifest_rejected():
    r = client.get("/pipelines/")
    assert r.status_code == 400


def test_manifest_path_traversal_rejected():
    r = client.get("/pipelines/", params={"manifest": "../demo_data/raw/orders.csv"})
    assert r.status_code == 400


def test_manifest_not_found():
    r = client.get("/pipelines/", params={"manifest": "nope.json"})
    assert r.status_code == 404


# --- database source (db=) ---

def test_db_url_rejected_over_api():
    r = client.get("/statistics/", params={"file": DEMO, "db": "postgres://u:p@h/db"})
    assert r.status_code == 400
    assert "not accepted over the API" in r.json()["detail"]


def test_db_path_traversal_rejected():
    r = client.get("/statistics/", params={"file": DEMO, "db": "../samples/sample_config.csv"})
    assert r.status_code == 400


def test_db_file_not_found():
    r = client.get("/statistics/", params={"file": DEMO, "db": "missing.duckdb"})
    assert r.status_code == 404


def test_data_dir_and_db_together_rejected():
    r = client.get("/statistics/", params={"file": DEMO, "data_dir": ".", "db": "x.duckdb"})
    assert r.status_code == 400


# --- /configs and /health ---

def test_list_configs_default_dir():
    r = client.get("/configs/")
    assert r.status_code == 200
    data = r.json()
    assert "demo_config.csv" in data["files"]
    assert "showcase_config.csv" in data["files"]
    assert "dbt_manifest_sample.json" in data["manifests"]


def test_health_reports_ok_and_version():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_health_api_alias():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- /tables ---

def test_list_tables_default_data_dir():
    r = client.get("/tables/")
    assert r.status_code == 200
    tables = r.json()["tables"]
    assert "raw.orders" in tables
    assert "staging.orders" in tables


def test_list_tables_data_dir_traversal_rejected():
    r = client.get("/tables/", params={"data_dir": "../samples"})
    assert r.status_code == 400


# --- thresholds / tolerance params ---

def test_findings_row_loss_tolerance_param():
    strict = client.get("/findings/", params={"file": DEMO, "data_dir": "."})
    assert any(f["finding_type"] == "row_count_drop" for f in strict.json())
    # demo etl_001 loses 10% — a 15% tolerance suppresses the warning
    tolerant = client.get(
        "/findings/", params={"file": DEMO, "data_dir": ".", "row_loss_tolerance": 15},
    )
    assert tolerant.status_code == 200
    assert not any(f["finding_type"] == "row_count_drop" for f in tolerant.json())


def test_profile_null_threshold_param():
    default = client.get("/profile/", params={"table": "staging.orders", "data_dir": "."})
    assert any(f["finding_type"] == "high_null_rate" for f in default.json()["findings"])
    relaxed = client.get(
        "/profile/",
        params={"table": "staging.orders", "data_dir": ".", "null_threshold": 90},
    )
    assert relaxed.status_code == 200
    assert not any(f["finding_type"] == "high_null_rate" for f in relaxed.json()["findings"])


def test_threshold_params_validated():
    r = client.get("/findings/", params={"file": DEMO, "row_loss_tolerance": 150})
    assert r.status_code == 422
