from pathlib import Path

import duckdb
import pytest

from app.adapters.local_file_data_source import LocalFileDataSource
from app.models.column_info import ColumnInfo


# ── fixtures helpers ──────────────────────────────────────────────────────────

def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_parquet(path: Path, csv_content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_csv = path.with_suffix(".tmp.csv")
    tmp_csv.write_text(csv_content, encoding="utf-8")
    safe_csv = tmp_csv.as_posix().replace("'", "''")
    safe_out = path.as_posix().replace("'", "''")
    duckdb.execute(
        f"COPY (SELECT * FROM read_csv_auto('{safe_csv}')) TO '{safe_out}' (FORMAT PARQUET)"
    )
    tmp_csv.unlink()


# ── resolution and existence ──────────────────────────────────────────────────

def test_table_exists_csv(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    assert LocalFileDataSource(tmp_path).table_exists("raw.orders") is True


def test_table_exists_parquet(tmp_path):
    _write_parquet(tmp_path / "raw" / "orders.parquet", "id,name\n1,Alice\n")
    assert LocalFileDataSource(tmp_path).table_exists("raw.orders") is True


def test_table_exists_missing(tmp_path):
    assert LocalFileDataSource(tmp_path).table_exists("raw.orders") is False


def test_table_exists_no_schema_prefix(tmp_path):
    _write_csv(tmp_path / "orders.csv", "id,name\n1,Alice\n")
    assert LocalFileDataSource(tmp_path).table_exists("orders") is True


def test_table_name_lowercased(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    assert LocalFileDataSource(tmp_path).table_exists("RAW.ORDERS") is True


def test_prefers_parquet_over_csv(tmp_path):
    # CSV has 3 rows, Parquet has 2 — Parquet must be chosen
    _write_csv(tmp_path / "raw" / "orders.csv", "id\n1\n2\n3\n")
    _write_parquet(tmp_path / "raw" / "orders.parquet", "id\n1\n2\n")
    assert LocalFileDataSource(tmp_path).get_row_count("raw.orders") == 2


# ── row count ─────────────────────────────────────────────────────────────────

def test_get_row_count_csv(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n2,Bob\n3,Charlie\n")
    assert LocalFileDataSource(tmp_path).get_row_count("raw.orders") == 3


def test_get_row_count_parquet(tmp_path):
    _write_parquet(tmp_path / "raw" / "orders.parquet", "id,name\n1,Alice\n2,Bob\n3,Charlie\n")
    assert LocalFileDataSource(tmp_path).get_row_count("raw.orders") == 3


# ── schema ────────────────────────────────────────────────────────────────────

def test_get_schema_column_names(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name,score\n1,Alice,90\n")
    schema = LocalFileDataSource(tmp_path).get_schema("raw.orders")
    assert [c.name for c in schema] == ["id", "name", "score"]


def test_get_schema_returns_column_info_objects(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    schema = LocalFileDataSource(tmp_path).get_schema("raw.orders")
    assert all(isinstance(c, ColumnInfo) for c in schema)


def test_get_schema_includes_dtype(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    schema = LocalFileDataSource(tmp_path).get_schema("raw.orders")
    assert all(c.dtype for c in schema)


# ── aggregate methods ─────────────────────────────────────────────────────────

def test_get_distinct_count(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,category\n1,A\n2,A\n3,B\n")
    assert LocalFileDataSource(tmp_path).get_distinct_count("raw.orders", "category") == 2


def test_get_null_count(tmp_path):
    # Empty field in a numeric column is NULL in DuckDB's CSV auto-detection
    _write_csv(tmp_path / "raw" / "orders.csv", "id,score\n1,90\n2,\n3,85\n")
    assert LocalFileDataSource(tmp_path).get_null_count("raw.orders", "score") == 1


def test_get_empty_string_count(tmp_path):
    # DuckDB reads unquoted empty CSV fields as NULL; a quoted "" is a genuine empty string.
    _write_csv(tmp_path / "raw" / "orders.csv", 'id,name\n1,Alice\n2,""\n3,Charlie\n')
    assert LocalFileDataSource(tmp_path).get_empty_string_count("raw.orders", "name") == 1


def test_get_duplicate_key_count_no_dupes(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n2,Bob\n3,Charlie\n")
    assert LocalFileDataSource(tmp_path).get_duplicate_key_count("raw.orders", "id") == 0


def test_get_duplicate_key_count_with_dupes(tmp_path):
    # Key 1 appears twice → 1 distinct key value with duplicates
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n1,Alice2\n2,Bob\n")
    assert LocalFileDataSource(tmp_path).get_duplicate_key_count("raw.orders", "id") == 1


def test_get_filtered_row_count(tmp_path):
    _write_csv(
        tmp_path / "raw" / "orders.csv",
        "id,status\n1,completed\n2,completed\n3,pending\n4,completed\n",
    )
    ds = LocalFileDataSource(tmp_path)
    assert ds.get_filtered_row_count("raw.orders", "status = 'completed'") == 3


def test_get_filtered_row_count_in_clause(tmp_path):
    _write_csv(
        tmp_path / "raw" / "orders.csv",
        "id,status\n1,completed\n2,pending\n3,cancelled\n",
    )
    ds = LocalFileDataSource(tmp_path)
    assert ds.get_filtered_row_count("raw.orders", "status IN ('completed', 'pending')") == 2


# ── cross-table join aggregates ─────────────────────────────────────────────────

def _join_fixtures(tmp_path):
    # left cid: 1,1,2,9 ; right id: 1,1,2  (right key 1 is duplicated)
    _write_csv(tmp_path / "raw" / "orders.csv", "cid\n1\n1\n2\n9\n")
    _write_csv(tmp_path / "raw" / "customers.csv", "id\n1\n1\n2\n")
    return LocalFileDataSource(tmp_path)


def test_get_join_output_row_count_inner(tmp_path):
    ds = _join_fixtures(tmp_path)
    # cid1 (x2 left) * id1 (x2) = 4 ; cid2 * id2 = 1 ; cid9 = 0  -> 5
    assert ds.get_join_output_row_count("raw.orders", "cid", "raw.customers", "id", "INNER") == 5


def test_get_join_output_row_count_left(tmp_path):
    ds = _join_fixtures(tmp_path)
    # INNER 5, plus the unmatched cid9 kept once -> 6
    assert ds.get_join_output_row_count("raw.orders", "cid", "raw.customers", "id", "LEFT") == 6


def test_get_unmatched_left_count(tmp_path):
    ds = _join_fixtures(tmp_path)
    # only cid9 has no matching right key
    assert ds.get_unmatched_left_count("raw.orders", "cid", "raw.customers", "id") == 1


def test_get_join_output_row_count_with_where(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "cid,flag\n1,y\n1,n\n2,y\n9,y\n")
    _write_csv(tmp_path / "raw" / "customers.csv", "id\n1\n1\n2\n")
    ds = LocalFileDataSource(tmp_path)
    # WHERE flag='y' keeps cid 1,2,9 ; INNER: cid1*id1(x2)=2, cid2=1, cid9=0 -> 3
    assert (
        ds.get_join_output_row_count(
            "raw.orders", "cid", "raw.customers", "id", "INNER", where_clause="flag = 'y'"
        )
        == 3
    )


# ── error handling ────────────────────────────────────────────────────────────

def test_missing_table_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalFileDataSource(tmp_path).get_row_count("raw.orders")


def test_missing_table_schema_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        LocalFileDataSource(tmp_path).get_schema("raw.orders")


def test_invalid_column_name_raises_value_error(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    with pytest.raises(ValueError, match="Invalid column name"):
        LocalFileDataSource(tmp_path).get_null_count("raw.orders", "my column")


def test_nonexistent_column_raises_value_error(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id,name\n1,Alice\n")
    with pytest.raises(ValueError, match="does not exist"):
        LocalFileDataSource(tmp_path).get_null_count("raw.orders", "nonexistent")


# ── list_tables ───────────────────────────────────────────────────────────────

def test_list_tables_nested_and_root(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id\n1\n")
    _write_csv(tmp_path / "staging" / "orders.csv", "id\n1\n")
    _write_csv(tmp_path / "lookup.csv", "id\n1\n")
    assert LocalFileDataSource(tmp_path).list_tables() == [
        "lookup", "raw.orders", "staging.orders",
    ]


def test_list_tables_dedupes_parquet_and_csv(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id\n1\n")
    _write_parquet(tmp_path / "raw" / "orders.parquet", "id\n1\n")
    assert LocalFileDataSource(tmp_path).list_tables() == ["raw.orders"]


def test_list_tables_missing_dir_empty(tmp_path):
    assert LocalFileDataSource(tmp_path / "nope").list_tables() == []


# ── single-pass profile counts ────────────────────────────────────────────────

def test_get_profile_counts_matches_per_column_methods(tmp_path):
    _write_csv(
        tmp_path / "raw" / "orders.csv",
        'id,note\n1,"a"\n2,""\n3,\n3,"a"\n',  # note: one empty string, one NULL
    )
    ds = LocalFileDataSource(tmp_path)
    row_count, counts = ds.get_profile_counts("raw.orders", ["id", "note"], {"note"})
    assert row_count == ds.get_row_count("raw.orders") == 4
    assert counts["id"]["null_count"] == ds.get_null_count("raw.orders", "id") == 0
    assert counts["id"]["distinct_count"] == ds.get_distinct_count("raw.orders", "id") == 3
    assert counts["id"]["empty_string_count"] is None  # not a text column
    assert counts["note"]["null_count"] == ds.get_null_count("raw.orders", "note") == 1
    assert counts["note"]["empty_string_count"] == ds.get_empty_string_count("raw.orders", "note") == 1


def test_get_profile_counts_invalid_column_raises(tmp_path):
    _write_csv(tmp_path / "raw" / "orders.csv", "id\n1\n")
    ds = LocalFileDataSource(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        ds.get_profile_counts("raw.orders", ["ghost"], set())
