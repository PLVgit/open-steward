import pytest
from pathlib import Path

from app.adapters.csv_adapter import CsvAdapter

_HEADERS = "config_key,pipeline_name,enabled,source_table,target_table,sql_query,execution_order,primary_key,load_type"


def _write(tmp_path: Path, content: str) -> str:
    p = tmp_path / "config.csv"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_valid_csv_returns_pipeline_jobs(tmp_path):
    path = _write(
        tmp_path,
        f"{_HEADERS}\netl_001,Load Orders,true,raw.orders,staging.orders,SELECT 1,1,order_id,full",
    )
    jobs = CsvAdapter(path).load()
    assert len(jobs) == 1
    assert jobs[0].config_key == "etl_001"
    assert jobs[0].pipeline_name == "Load Orders"
    assert jobs[0].source_table == "raw.orders"
    assert jobs[0].target_table == "staging.orders"
    assert jobs[0].sql_query == "SELECT 1"
    assert jobs[0].execution_order == 1
    assert jobs[0].primary_key == "order_id"
    assert jobs[0].load_type == "full"


def test_enabled_field_parsed_as_bool(tmp_path):
    rows = "\n".join([
        _HEADERS,
        "etl_001,A,true,src,tgt,,,,",
        "etl_002,B,false,src,tgt,,,,",
        "etl_003,C,1,src,tgt,,,,",
        "etl_004,D,0,src,tgt,,,,",
    ])
    path = _write(tmp_path, rows)
    jobs = CsvAdapter(path).load()
    assert jobs[0].enabled is True
    assert jobs[1].enabled is False
    assert jobs[2].enabled is True
    assert jobs[3].enabled is False


def test_optional_fields_default_to_none(tmp_path):
    path = _write(
        tmp_path,
        "config_key,pipeline_name,enabled,source_table,target_table\netl_001,A,true,src,tgt",
    )
    jobs = CsvAdapter(path).load()
    assert jobs[0].sql_query is None
    assert jobs[0].execution_order is None
    assert jobs[0].primary_key is None
    assert jobs[0].load_type is None


def test_missing_required_column_raises(tmp_path):
    path = _write(
        tmp_path,
        "pipeline_name,enabled,source_table,target_table\nA,true,src,tgt",
    )
    with pytest.raises(ValueError, match="config_key"):
        CsvAdapter(path).load()


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        CsvAdapter("/nonexistent/path/config.csv").load()


def test_empty_csv_returns_empty_list(tmp_path):
    path = _write(tmp_path, _HEADERS + "\n")
    assert CsvAdapter(path).load() == []


def test_extra_columns_are_ignored(tmp_path):
    path = _write(
        tmp_path,
        f"{_HEADERS},extra_col\netl_001,Load Orders,true,raw.orders,staging.orders,,,,,unexpected",
    )
    jobs = CsvAdapter(path).load()
    assert len(jobs) == 1
    assert jobs[0].config_key == "etl_001"


def test_short_row_raises_clear_error(tmp_path):
    # A row with fewer cells than the header must fail with a clear message,
    # not an AttributeError from a None cell.
    path = _write(tmp_path, f"{_HEADERS}\netl_001,Load Orders,true")
    with pytest.raises(ValueError, match=r"Row 2.*source_table"):
        CsvAdapter(path).load()


def test_empty_required_value_raises_clear_error(tmp_path):
    path = _write(tmp_path, f"{_HEADERS}\netl_001,,true,src,tgt,,,,")
    with pytest.raises(ValueError, match=r"Row 2.*pipeline_name"):
        CsvAdapter(path).load()


def test_error_reports_correct_row_number(tmp_path):
    rows = "\n".join([
        _HEADERS,
        "etl_001,A,true,src,tgt,,,,",
        "etl_002,,true,src,tgt,,,,",
    ])
    path = _write(tmp_path, rows)
    with pytest.raises(ValueError, match=r"Row 3.*pipeline_name"):
        CsvAdapter(path).load()


def test_invalid_execution_order_raises_clear_error(tmp_path):
    path = _write(tmp_path, f"{_HEADERS}\netl_001,A,true,src,tgt,,abc,,")
    with pytest.raises(ValueError, match=r"Row 2.*execution_order"):
        CsvAdapter(path).load()
