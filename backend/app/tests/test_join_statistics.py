from pathlib import Path

from app.adapters.local_file_data_source import LocalFileDataSource
from app.models.pipeline_job import PipelineJob
from app.services.join_statistics import analyze_job_join


def _csv(data_dir: Path, table: str, content: str) -> None:
    parts = table.split(".", maxsplit=1)
    path = (
        data_dir / parts[0] / f"{parts[1]}.csv"
        if len(parts) == 2
        else data_dir / f"{parts[0]}.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _job(sql: str, source: str = "raw.orders", target: str = "mart.out") -> PipelineJob:
    return PipelineJob(
        config_key="etl_join",
        pipeline_name="Join Job",
        enabled=True,
        source_table=source,
        target_table=target,
        primary_key=None,
        load_type="full",
        sql_query=sql,
    )


INNER_SQL = "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id"
LEFT_SQL = "SELECT * FROM raw.orders o LEFT JOIN raw.customers c ON o.cid = c.id"


def _types(findings):
    return [f.finding_type for f in findings]


# ── staged explanation ───────────────────────────────────────────────────────

def test_explained_inner_join_all_matched(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n3\n")
    _csv(tmp_path, "raw.customers", "id\n1\n2\n3\n")
    ds = LocalFileDataSource(tmp_path)
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=3, target_count=3)
    assert _types(findings) == ["row_count_change_explained_by_transformations"]
    assert findings[0].severity == "info"


def test_left_join_fanout_explained_with_multiplication_advisory(tmp_path):
    # right key 1 duplicated -> LEFT join multiplies the matching left row
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n")
    _csv(tmp_path, "raw.customers", "id\n1\n1\n2\n")
    ds = LocalFileDataSource(tmp_path)
    # expected_after_join: cid1 -> 2, cid2 -> 1 = 3
    findings = analyze_job_join(_job(LEFT_SQL), ds, source_count=2, target_count=3)
    types = _types(findings)
    assert "row_count_change_explained_by_transformations" in types
    assert "possible_row_multiplication" in types


def test_inner_join_unmatched_explained_with_unmatched_advisory(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n9\n")
    _csv(tmp_path, "raw.customers", "id\n1\n2\n")
    ds = LocalFileDataSource(tmp_path)
    # INNER drops cid9 -> expected 2
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=3, target_count=2)
    types = _types(findings)
    assert "row_count_change_explained_by_transformations" in types
    unmatched = next(f for f in findings if f.finding_type == "join_unmatched_rows")
    assert unmatched.severity == "warning"  # INNER drops them
    assert "unmatched_left_rows=1" in unmatched.message


def test_unexpected_row_loss_after_join(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n3\n")
    _csv(tmp_path, "raw.customers", "id\n1\n2\n3\n")
    ds = LocalFileDataSource(tmp_path)
    # expected 3 but target only 2
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=3, target_count=2)
    loss = next(f for f in findings if f.finding_type == "unexpected_row_loss_after_join")
    assert loss.severity == "warning"
    assert "expected_after_join_count=3" in loss.message
    assert "unexpected_loss_rows=1" in loss.message


def test_unexpected_row_surplus_after_join(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n3\n")
    _csv(tmp_path, "raw.customers", "id\n1\n2\n3\n")
    ds = LocalFileDataSource(tmp_path)
    # expected 3 but target has 5
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=3, target_count=5)
    surplus = next(f for f in findings if f.finding_type == "unexpected_row_surplus_after_join")
    assert surplus.severity == "warning"
    assert "unexpected_surplus_rows=2" in surplus.message


def test_staged_where_then_join(tmp_path):
    _csv(tmp_path, "raw.orders", "cid,status\n1,completed\n2,completed\n9,pending\n")
    _csv(tmp_path, "raw.customers", "id\n1\n2\n")
    ds = LocalFileDataSource(tmp_path)
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "WHERE o.status = 'completed'"
    )
    # after_filter: cid 1,2 (2 rows) ; INNER join -> 2 ; target 2 -> explained
    findings = analyze_job_join(_job(sql), ds, source_count=3, target_count=2)
    explained = next(
        f for f in findings if f.finding_type == "row_count_change_explained_by_transformations"
    )
    assert "after_filter_count=2" in explained.message
    assert "filtered_out_rows=1" in explained.message


# ── advisory: nulls and many-to-many ─────────────────────────────────────────

def test_join_key_nulls_advisory(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n\n")  # one null key
    _csv(tmp_path, "raw.customers", "id\n1\n2\n")
    ds = LocalFileDataSource(tmp_path)
    # null + matched 1,2 -> expected 2 ; target 2
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=3, target_count=2)
    assert "join_key_nulls" in _types(findings)


def test_many_to_many_advisory(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n1\n")  # left dup
    _csv(tmp_path, "raw.customers", "id\n1\n1\n")  # right dup
    ds = LocalFileDataSource(tmp_path)
    # 2x2 = 4 expected
    findings = analyze_job_join(_job(INNER_SQL), ds, source_count=2, target_count=4)
    types = _types(findings)
    assert "possible_many_to_many_join" in types
    assert "possible_row_multiplication" not in types  # superseded by many-to-many


# ── fall back to None ────────────────────────────────────────────────────────

def test_missing_right_table_returns_none(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n2\n")  # no customers snapshot
    ds = LocalFileDataSource(tmp_path)
    assert analyze_job_join(_job(INNER_SQL), ds, source_count=2, target_count=2) is None


def test_left_table_not_source_returns_none(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n")
    _csv(tmp_path, "raw.customers", "id\n1\n")
    ds = LocalFileDataSource(tmp_path)
    # job declares a different source table than the join's left table
    job = _job(INNER_SQL, source="raw.other")
    assert analyze_job_join(job, ds, source_count=1, target_count=1) is None


def test_non_join_sql_returns_none(tmp_path):
    _csv(tmp_path, "raw.orders", "cid\n1\n")
    ds = LocalFileDataSource(tmp_path)
    job = _job("SELECT * FROM raw.orders WHERE cid = 1")
    assert analyze_job_join(job, ds, source_count=1, target_count=1) is None
