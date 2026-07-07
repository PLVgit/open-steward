from pathlib import Path

import pytest

from app.adapters.local_file_data_source import LocalFileDataSource
from app.models.pipeline_job import PipelineJob
from app.services.reconciliation_engine import reconcile_jobs


# ── helpers ───────────────────────────────────────────────────────────────────

def _csv(data_dir: Path, table: str, content: str) -> None:
    parts = table.split(".", maxsplit=1)
    path = (
        data_dir / parts[0] / f"{parts[1]}.csv"
        if len(parts) == 2
        else data_dir / f"{parts[0]}.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _job(
    source: str = "raw.orders",
    target: str = "staging.orders",
    enabled: bool = True,
    pk: str | None = "id",
    load_type: str | None = "full",
    key: str = "etl_001",
    sql: str | None = None,
) -> PipelineJob:
    return PipelineJob(
        config_key=key,
        pipeline_name="Test Job",
        enabled=enabled,
        source_table=source,
        target_table=target,
        primary_key=pk,
        load_type=load_type,
        sql_query=sql,
    )


ORDERS_3 = "id,name\n1,Alice\n2,Bob\n3,Charlie\n"
ORDERS_2 = "id,name\n1,Alice\n2,Bob\n"
ORDERS_EMPTY = "id,name\n"  # headers only, 0 data rows


# ── empty_target ──────────────────────────────────────────────────────────────

def test_empty_target_warning(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    types = [f.finding_type for f in findings]
    assert "empty_target" in types
    assert findings[types.index("empty_target")].severity == "warning"


def test_empty_target_message_includes_counts(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    msg = next(f.message for f in findings if f.finding_type == "empty_target")
    assert "source_count=3" in msg
    assert "target_count=0" in msg


def test_both_empty_no_empty_target_finding(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_EMPTY)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, load_type=None)], ds)
    assert not any(f.finding_type == "empty_target" for f in findings)


# ── row_count_drop ────────────────────────────────────────────────────────────

def test_row_count_drop_warning(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    types = [f.finding_type for f in findings]
    assert "row_count_drop" in types
    assert findings[types.index("row_count_drop")].severity == "warning"


def test_row_count_drop_message_includes_metrics(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    msg = next(f.message for f in findings if f.finding_type == "row_count_drop")
    assert "source_count=3" in msg
    assert "target_count=2" in msg
    assert "lost_rows=1" in msg
    assert "loss_pct=" in msg


def test_full_load_equal_counts_no_finding(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_3)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    assert not any(f.finding_type == "row_count_drop" for f in findings)


def test_incremental_load_no_row_count_drop(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, load_type="incremental")], ds)
    assert not any(f.finding_type == "row_count_drop" for f in findings)


def test_row_count_drop_not_fired_when_target_empty(tmp_path):
    # empty_target covers this case; row_count_drop should not also fire
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    assert not any(f.finding_type == "row_count_drop" for f in findings)
    assert any(f.finding_type == "empty_target" for f in findings)


# ── null_primary_key ──────────────────────────────────────────────────────────

def test_null_primary_key_error(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    # Empty unquoted field in numeric column → NULL in DuckDB
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n,Bob\n3,Charlie\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    types = [f.finding_type for f in findings]
    assert "null_primary_key" in types
    assert findings[types.index("null_primary_key")].severity == "error"


def test_null_primary_key_message_includes_metrics(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n,Bob\n3,Charlie\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    msg = next(f.message for f in findings if f.finding_type == "null_primary_key")
    assert "null_count=1" in msg
    assert "target_count=3" in msg
    assert "null_pct=" in msg
    assert "id" in msg
    assert "staging.orders" in msg


def test_no_null_primary_key_no_finding(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_3)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    assert not any(f.finding_type == "null_primary_key" for f in findings)


# ── duplicate_primary_key ─────────────────────────────────────────────────────

def test_duplicate_primary_key_error(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n1,Alice2\n2,Bob\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    types = [f.finding_type for f in findings]
    assert "duplicate_primary_key" in types
    assert findings[types.index("duplicate_primary_key")].severity == "error"


def test_duplicate_primary_key_message_includes_metrics(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n1,Alice2\n2,Bob\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    msg = next(f.message for f in findings if f.finding_type == "duplicate_primary_key")
    assert "duplicate_key_count=1" in msg
    assert "target_count=3" in msg
    assert "id" in msg
    assert "staging.orders" in msg


def test_no_duplicate_primary_key_no_finding(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_3)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    assert not any(f.finding_type == "duplicate_primary_key" for f in findings)


# ── skip conditions ───────────────────────────────────────────────────────────

def test_disabled_job_skipped(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(enabled=False)], ds)
    assert findings == []


def test_source_missing_skipped(tmp_path):
    _csv(tmp_path, "staging.orders", ORDERS_3)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    assert findings == []


def test_target_missing_skipped(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    assert findings == []


def test_no_primary_key_skips_pk_checks(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    # Target has duplicate IDs — but no primary_key set, so no PK checks run
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n1,Alice2\n2,Bob\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)
    assert not any(f.finding_type in ("duplicate_primary_key", "null_primary_key") for f in findings)


def test_misconfigured_primary_key_skips_pk_checks(tmp_path):
    # The configured PK column doesn't exist in the target snapshot. That must
    # not break the whole report — PK checks are skipped, other findings stand.
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk="nonexistent_col")], ds)
    types = [f.finding_type for f in findings]
    assert "null_primary_key" not in types
    assert "duplicate_primary_key" not in types
    assert "row_count_drop" in types  # the 3 → 2 drop is still reported


# ── finding metadata ──────────────────────────────────────────────────────────

def test_affected_job_set_correctly(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_EMPTY)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, key="etl_042")], ds)
    assert all(f.affected_job == "etl_042" for f in findings)


def test_affected_table_on_pk_findings(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n1,Alice2\n2,Bob\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    pk_findings = [f for f in findings if f.finding_type == "duplicate_primary_key"]
    assert all(f.affected_table == "staging.orders" for f in pk_findings)


# ── multiple findings ─────────────────────────────────────────────────────────

def test_multiple_findings_same_job(tmp_path):
    # Source: 3 rows. Target: 2 rows with duplicate PK → row_count_drop + duplicate_primary_key
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", "id,name\n1,Alice\n1,Alice2\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job()], ds)
    types = [f.finding_type for f in findings]
    assert "row_count_drop" in types
    assert "duplicate_primary_key" in types


# ── filter-aware reconciliation (Ticket 21) ─────────────────────────────────────

# 5 rows, 3 with status='completed'
SRC_STATUS = "id,status\n1,completed\n2,completed\n3,pending\n4,completed\n5,cancelled\n"
TGT_3_COMPLETED = "id,status\n1,completed\n2,completed\n4,completed\n"  # 3 rows
FILTER_SQL = "SELECT * FROM raw.orders WHERE status = 'completed'"


def test_row_loss_fully_explained_by_filter(tmp_path):
    _csv(tmp_path, "raw.orders", SRC_STATUS)
    _csv(tmp_path, "staging.orders", TGT_3_COMPLETED)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, sql=FILTER_SQL)], ds)
    types = [f.finding_type for f in findings]
    assert "row_loss_explained_by_filter" in types
    assert "row_count_drop" not in types
    assert "unexpected_row_loss" not in types
    explained = next(f for f in findings if f.finding_type == "row_loss_explained_by_filter")
    assert explained.severity == "info"
    assert "source_count=5" in explained.message
    assert "expected_after_filter_count=3" in explained.message
    assert "target_count=3" in explained.message
    assert "filtered_out_rows=2" in explained.message


def test_unexpected_row_loss_after_filter(tmp_path):
    _csv(tmp_path, "raw.orders", SRC_STATUS)
    # Only 2 rows in target, but the filter would yield 3 → 1 unexpected lost row
    _csv(tmp_path, "staging.orders", "id,status\n1,completed\n2,completed\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, sql=FILTER_SQL)], ds)
    types = [f.finding_type for f in findings]
    assert "unexpected_row_loss" in types
    assert "row_count_drop" not in types
    assert "row_loss_explained_by_filter" not in types
    loss = next(f for f in findings if f.finding_type == "unexpected_row_loss")
    assert loss.severity == "warning"
    assert "expected_after_filter_count=3" in loss.message
    assert "target_count=2" in loss.message
    assert "unexpected_loss_rows=1" in loss.message


def test_no_filter_falls_back_to_row_count_drop(tmp_path):
    _csv(tmp_path, "raw.orders", SRC_STATUS)
    _csv(tmp_path, "staging.orders", TGT_3_COMPLETED)
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, sql="SELECT * FROM raw.orders")], ds)
    types = [f.finding_type for f in findings]
    assert "row_count_drop" in types
    assert "row_loss_explained_by_filter" not in types
    assert "unexpected_row_loss" not in types


def test_join_sql_without_right_snapshot_falls_back_to_row_count_drop(tmp_path):
    # The join's right table has no snapshot, so join analysis can't run and the
    # job falls back to the plain row_count_drop (target < source).
    _csv(tmp_path, "raw.orders", SRC_STATUS)
    _csv(tmp_path, "staging.orders", TGT_3_COMPLETED)
    join_sql = (
        "SELECT o.id FROM raw.orders o JOIN raw.customers c ON o.id = c.id "
        "WHERE o.status = 'completed'"
    )
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None, sql=join_sql)], ds)
    types = [f.finding_type for f in findings]
    assert "row_count_drop" in types
    assert "unexpected_row_loss" not in types


# ── join-aware staged reconciliation through reconcile_jobs (Ticket 22) ──────────

def test_join_job_surfaces_staged_finding(tmp_path):
    # raw.orders (3) LEFT JOIN raw.customers; right key 1 duplicated -> 4 rows.
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n3\n")
    _csv(tmp_path, "raw.customers", "id\n1\n1\n2\n3\n")
    _csv(tmp_path, "mart.out", "cid,id\n1,1\n1,1\n2,2\n3,3\n")  # 4 rows = expected
    job = PipelineJob(
        config_key="etl_join",
        pipeline_name="Join Job",
        enabled=True,
        source_table="raw.orders",
        target_table="mart.out",
        primary_key=None,
        load_type="full",
        sql_query="SELECT * FROM raw.orders o LEFT JOIN raw.customers c ON o.cid = c.id",
    )
    ds = LocalFileDataSource(tmp_path)
    types = [f.finding_type for f in reconcile_jobs([job], ds)]
    assert "row_count_change_explained_by_transformations" in types
    assert "possible_row_multiplication" in types


# ── row-loss tolerance ────────────────────────────────────────────────────────

def test_row_loss_tolerance_suppresses_small_drop(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)  # 3 → 2 = 33.3% loss
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds, row_loss_tolerance_pct=50.0)
    assert not any(f.finding_type == "row_count_drop" for f in findings)


def test_row_loss_tolerance_still_flags_larger_drop(tmp_path):
    _csv(tmp_path, "raw.orders", ORDERS_3)
    _csv(tmp_path, "staging.orders", ORDERS_2)  # 33.3% loss > 10% tolerance
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds, row_loss_tolerance_pct=10.0)
    assert any(f.finding_type == "row_count_drop" for f in findings)


def test_zero_tolerance_default_never_suppresses(tmp_path):
    # A 1-row loss out of many rounds to 0.0% in messages, but the default
    # tolerance must still flag it (comparison uses the unrounded pct).
    _csv(tmp_path, "raw.orders", "id\n" + "\n".join(str(i) for i in range(1, 2001)) + "\n")
    _csv(tmp_path, "staging.orders", "id\n" + "\n".join(str(i) for i in range(1, 2000)) + "\n")
    ds = LocalFileDataSource(tmp_path)
    findings = reconcile_jobs([_job(pk=None)], ds)  # default tolerance 0.0
    assert any(f.finding_type == "row_count_drop" for f in findings)


def test_row_loss_tolerance_applies_to_filter_unexpected_loss(tmp_path):
    # WHERE explains 3 → 2; target has 1 more row missing (50% of expected).
    _csv(tmp_path, "raw.orders", "id,status\n1,paid\n2,paid\n3,other\n")
    _csv(tmp_path, "staging.orders", "id,status\n1,paid\n")
    ds = LocalFileDataSource(tmp_path)
    job = _job(pk=None, sql="SELECT * FROM raw.orders WHERE status = 'paid'")

    strict = reconcile_jobs([job], ds)
    assert any(f.finding_type == "unexpected_row_loss" for f in strict)

    tolerant = reconcile_jobs([job], ds, row_loss_tolerance_pct=60.0)
    assert not any(f.finding_type == "unexpected_row_loss" for f in tolerant)


def test_row_loss_tolerance_applies_to_join_loss(tmp_path):
    # INNER join with all keys matching (unique right) => expected 4; target 3
    # (25% unexpected loss). Tolerance 30 suppresses; strict flags.
    _csv(tmp_path, "raw.orders", "id,k\n1,a\n2,b\n3,c\n4,d\n")
    _csv(tmp_path, "raw.dim", "k,name\na,x\nb,y\nc,z\nd,w\n")
    _csv(tmp_path, "staging.orders", "id\n1\n2\n3\n")
    ds = LocalFileDataSource(tmp_path)
    job = _job(
        pk=None,
        sql="SELECT o.id FROM raw.orders o INNER JOIN raw.dim d ON o.k = d.k",
    )

    strict = reconcile_jobs([job], ds)
    assert any(f.finding_type == "unexpected_row_loss_after_join" for f in strict)

    tolerant = reconcile_jobs([job], ds, row_loss_tolerance_pct=30.0)
    assert not any(f.finding_type == "unexpected_row_loss_after_join" for f in tolerant)
