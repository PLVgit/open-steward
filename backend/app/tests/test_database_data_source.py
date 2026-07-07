from pathlib import Path

import duckdb
import pytest

from app.adapters.database_data_source import DatabaseDataSource, _expand_env
from app.models.pipeline_job import PipelineJob
from app.services.reconciliation_engine import reconcile_jobs


# ── fixture ───────────────────────────────────────────────────────────────────

def _make_db(tmp_path: Path) -> str:
    """Create a small warehouse.duckdb with raw + staging schemas."""
    path = tmp_path / "warehouse.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute("CREATE SCHEMA raw; CREATE SCHEMA staging;")
    conn.execute("""
        CREATE TABLE raw.orders AS
        SELECT * FROM (VALUES
            (1, 'completed', 'A'),
            (2, 'completed', ''),
            (3, 'pending',   NULL),
            (4, 'completed', 'B')
        ) AS t(id, status, note)
    """)
    conn.execute("""
        CREATE TABLE staging.orders AS
        SELECT * FROM (VALUES
            (1, 'completed'),
            (2, 'completed'),
            (2, 'completed')
        ) AS t(id, status)
    """)
    conn.execute("""
        CREATE TABLE staging.customers AS
        SELECT * FROM (VALUES (1, 'Alice'), (2, 'Bob'), (2, 'Bob2')) AS t(id, name)
    """)
    conn.close()
    return str(path)


@pytest.fixture()
def ds(tmp_path) -> DatabaseDataSource:
    return DatabaseDataSource(_make_db(tmp_path))


# ── existence / resolution ────────────────────────────────────────────────────

def test_table_exists(ds):
    assert ds.table_exists("raw.orders") is True
    assert ds.table_exists("raw.missing") is False
    assert ds.table_exists("nope.nope") is False


def test_invalid_table_name_never_reaches_sql(ds):
    assert ds.table_exists("raw.orders; DROP TABLE x") is False
    with pytest.raises(ValueError, match="Invalid table name"):
        ds.get_row_count("raw.orders--")


def test_missing_database_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No database file"):
        DatabaseDataSource(str(tmp_path / "missing.duckdb"))


# ── aggregates ────────────────────────────────────────────────────────────────

def test_row_count(ds):
    assert ds.get_row_count("raw.orders") == 4
    assert ds.get_row_count("staging.orders") == 3


def test_schema(ds):
    names = [c.name for c in ds.get_schema("raw.orders")]
    assert names == ["id", "status", "note"]


def test_null_and_empty_string_counts(ds):
    assert ds.get_null_count("raw.orders", "note") == 1
    assert ds.get_empty_string_count("raw.orders", "note") == 1


def test_distinct_count(ds):
    assert ds.get_distinct_count("raw.orders", "status") == 2


def test_duplicate_key_count(ds):
    assert ds.get_duplicate_key_count("staging.orders", "id") == 1  # id=2 twice


def test_filtered_row_count(ds):
    assert ds.get_filtered_row_count("raw.orders", "status = 'completed'") == 3


def test_join_output_row_count(ds):
    # staging.orders ids (1,2,2) × staging.customers ids (1,2,2):
    # INNER: 1→1 match, 2→2 matches each for two left rows = 1 + 2 + 2 = 5
    assert ds.get_join_output_row_count("staging.orders", "id", "staging.customers", "id", "INNER") == 5


def test_unmatched_left_count(ds):
    # raw.orders ids 1..4 vs customers ids (1,2,2) → 3 and 4 unmatched
    assert ds.get_unmatched_left_count("raw.orders", "id", "staging.customers", "id") == 2


def test_invalid_column_raises(ds):
    with pytest.raises(ValueError, match="does not exist"):
        ds.get_null_count("raw.orders", "ghost")


# ── engine integration ────────────────────────────────────────────────────────

def test_reconciliation_works_over_database(tmp_path):
    ds = DatabaseDataSource(_make_db(tmp_path))
    job = PipelineJob(
        config_key="etl_db",
        pipeline_name="DB job",
        enabled=True,
        source_table="raw.orders",
        target_table="staging.orders",
        primary_key="id",
        load_type="full",
    )
    types = {f.finding_type for f in reconcile_jobs([job], ds)}
    assert "row_count_drop" in types          # 4 → 3
    assert "duplicate_primary_key" in types   # id=2 duplicated


# ── credentials ───────────────────────────────────────────────────────────────

def test_env_var_expansion(monkeypatch):
    monkeypatch.setenv("OS_TEST_PW", "s3cret")
    assert _expand_env("postgres://u:${OS_TEST_PW}@h/db") == "postgres://u:s3cret@h/db"
    # Unset variables are left as-is (no silent empty credentials).
    assert _expand_env("postgres://u:${OS_UNSET_VAR}@h/db") == "postgres://u:${OS_UNSET_VAR}@h/db"


def test_redact_url_masks_credentials():
    from app.adapters.database_data_source import _redact_url

    assert _redact_url("postgres://user:s3cret@host:5432/db") == "postgres://***@host:5432/db"
    assert _redact_url("postgres://host/db") == "postgres://host/db"  # nothing to mask


# ── connection error handling ─────────────────────────────────────────────────

def test_corrupt_database_file_raises_clear_error(tmp_path):
    bogus = tmp_path / "not_a_db.duckdb"
    bogus.write_text("this is not a duckdb file", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not open database file"):
        DatabaseDataSource(str(bogus))


# ── list_tables ───────────────────────────────────────────────────────────────

def test_list_tables_from_database(ds):
    tables = ds.list_tables()
    assert "raw.orders" in tables
    assert "staging.orders" in tables
    assert "staging.customers" in tables
    assert not any(t.startswith("information_schema") for t in tables)
