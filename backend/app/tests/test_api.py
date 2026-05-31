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
