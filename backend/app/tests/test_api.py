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
