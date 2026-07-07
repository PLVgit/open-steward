"""Environment-configurable directories: point the served API/UI at YOUR
project via OPEN_STEWARD_CONFIG_DIR / OPEN_STEWARD_DATA_DIR (defaults stay the
bundled samples/ and demo_data/)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_CSV = (
    "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
    "etl_mine,My Job,true,raw.orders,staging.orders,id,full\n"
)


def _make_config_dir(tmp_path: Path) -> Path:
    cfg = tmp_path / "my_configs"
    cfg.mkdir()
    (cfg / "mine.csv").write_text(_CSV, encoding="utf-8")
    return cfg


def _make_data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "my_data"
    (data / "raw").mkdir(parents=True)
    (data / "staging").mkdir(parents=True)
    (data / "raw" / "orders.csv").write_text("id\n1\n2\n3\n", encoding="utf-8")
    (data / "staging" / "orders.csv").write_text("id\n1\n2\n", encoding="utf-8")
    return data


def test_config_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_STEWARD_CONFIG_DIR", str(_make_config_dir(tmp_path)))
    r = client.get("/pipelines/", params={"file": "mine.csv"})
    assert r.status_code == 200
    assert r.json()[0]["config_key"] == "etl_mine"


def test_config_dir_override_lists_in_configs_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_STEWARD_CONFIG_DIR", str(_make_config_dir(tmp_path)))
    r = client.get("/configs/")
    assert r.status_code == 200
    assert r.json()["files"] == ["mine.csv"]
    assert r.json()["manifests"] == []


def test_config_dir_override_still_confined(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_STEWARD_CONFIG_DIR", str(_make_config_dir(tmp_path)))
    r = client.get("/pipelines/", params={"file": "../../backend/samples/demo_config.csv"})
    assert r.status_code == 400


def test_data_dir_override_drives_statistics(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_STEWARD_CONFIG_DIR", str(_make_config_dir(tmp_path)))
    monkeypatch.setenv("OPEN_STEWARD_DATA_DIR", str(_make_data_dir(tmp_path)))
    r = client.get("/statistics/", params={"file": "mine.csv"})
    assert r.status_code == 200
    s = r.json()[0]
    assert s["source_count"] == 3
    assert s["target_count"] == 2
    assert s["lost_rows"] == 1


def test_defaults_unchanged_without_env(monkeypatch):
    monkeypatch.delenv("OPEN_STEWARD_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OPEN_STEWARD_DATA_DIR", raising=False)
    r = client.get("/pipelines/", params={"file": "demo_config.csv"})
    assert r.status_code == 200  # bundled samples still the default
