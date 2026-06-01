from pathlib import Path

import pytest

from app.adapters.local_file_data_source import LocalFileDataSource
from app.models.table_profile import ColumnProfile, TableProfile
from app.services.dq_profiler import detect_profile_findings, profile_table


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


def _col(
    column_name: str = "score",
    dtype: str = "BIGINT",
    row_count: int = 100,
    null_count: int = 0,
    null_pct: float = 0.0,
    distinct_count: int = 50,
    distinct_pct: float = 50.0,
    empty_string_count: int | None = None,
    empty_string_pct: float | None = None,
) -> ColumnProfile:
    return ColumnProfile(
        column_name=column_name,
        dtype=dtype,
        row_count=row_count,
        null_count=null_count,
        null_pct=null_pct,
        distinct_count=distinct_count,
        distinct_pct=distinct_pct,
        empty_string_count=empty_string_count,
        empty_string_pct=empty_string_pct,
    )


def _profile(columns: list[ColumnProfile], table_name: str = "staging.orders") -> TableProfile:
    return TableProfile(
        table_name=table_name,
        row_count=columns[0].row_count if columns else 0,
        column_count=len(columns),
        columns=columns,
    )


# ── profile_table ─────────────────────────────────────────────────────────────

def test_profile_table_row_count(tmp_path):
    _csv(tmp_path, "raw.orders", "id,name\n1,Alice\n2,Bob\n3,Charlie\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    assert result.row_count == 3


def test_profile_table_column_count(tmp_path):
    _csv(tmp_path, "raw.orders", "id,name,score\n1,Alice,90\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    assert result.column_count == 3


def test_profile_table_name_set(tmp_path):
    _csv(tmp_path, "raw.orders", "id,name\n1,Alice\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    assert result.table_name == "raw.orders"


def test_profile_column_names(tmp_path):
    _csv(tmp_path, "raw.orders", "id,name,score\n1,Alice,90\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    assert [c.column_name for c in result.columns] == ["id", "name", "score"]


def test_profile_null_count_and_pct(tmp_path):
    # Empty field in integer column → NULL in DuckDB
    _csv(tmp_path, "raw.orders", "id,score\n1,90\n2,\n3,85\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    score = next(c for c in result.columns if c.column_name == "score")
    assert score.null_count == 1
    assert score.null_pct == 33.3


def test_profile_zero_nulls(tmp_path):
    _csv(tmp_path, "raw.orders", "id,name\n1,Alice\n2,Bob\n3,Charlie\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    for col in result.columns:
        assert col.null_count == 0
        assert col.null_pct == 0.0


def test_profile_distinct_count(tmp_path):
    _csv(tmp_path, "raw.orders", "id,category\n1,A\n2,A\n3,B\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    cat = next(c for c in result.columns if c.column_name == "category")
    assert cat.distinct_count == 2
    assert cat.distinct_pct == 66.7


def test_profile_empty_string_varchar(tmp_path):
    # Quoted "" in CSV is a genuine empty string with allow_quoted_nulls=false
    _csv(tmp_path, "raw.orders", 'id,name\n1,Alice\n2,""\n3,Charlie\n')
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    name_col = next(c for c in result.columns if c.column_name == "name")
    assert name_col.empty_string_count == 1
    assert name_col.empty_string_pct == 33.3


def test_profile_empty_string_none_for_numeric(tmp_path):
    _csv(tmp_path, "raw.orders", "id,score\n1,90\n2,85\n3,92\n")
    result = profile_table("raw.orders", LocalFileDataSource(tmp_path))
    score = next(c for c in result.columns if c.column_name == "score")
    assert score.empty_string_count is None
    assert score.empty_string_pct is None


def test_profile_missing_table_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        profile_table("raw.orders", LocalFileDataSource(tmp_path))


# ── detect_profile_findings — null checks ────────────────────────────────────

def test_detect_all_nulls_error():
    col = _col(null_count=100, null_pct=100.0, distinct_count=0)
    findings = detect_profile_findings(_profile([col]))
    types = [f.finding_type for f in findings]
    assert "all_nulls" in types
    assert next(f for f in findings if f.finding_type == "all_nulls").severity == "error"


def test_detect_all_nulls_suppresses_high_null_rate():
    col = _col(null_count=100, null_pct=100.0, distinct_count=0)
    findings = detect_profile_findings(_profile([col]))
    assert not any(f.finding_type == "high_null_rate" for f in findings)


def test_detect_high_null_rate_warning():
    col = _col(null_count=25, null_pct=25.0, distinct_count=10)
    findings = detect_profile_findings(_profile([col]))
    types = [f.finding_type for f in findings]
    assert "high_null_rate" in types
    assert next(f for f in findings if f.finding_type == "high_null_rate").severity == "warning"


def test_detect_below_null_threshold_no_finding():
    col = _col(null_count=10, null_pct=10.0, distinct_count=20)
    findings = detect_profile_findings(_profile([col]))
    assert not any(f.finding_type in ("all_nulls", "high_null_rate") for f in findings)


def test_detect_custom_null_threshold():
    # 33% nulls — below the custom 50% threshold, so no finding
    col = _col(null_count=33, null_pct=33.0, distinct_count=10)
    findings = detect_profile_findings(_profile([col]), null_rate_threshold_pct=50.0)
    assert not any(f.finding_type in ("all_nulls", "high_null_rate") for f in findings)


# ── detect_profile_findings — constant column ─────────────────────────────────

def test_detect_constant_column_info():
    col = _col(distinct_count=1, distinct_pct=1.0, row_count=100)
    findings = detect_profile_findings(_profile([col]))
    types = [f.finding_type for f in findings]
    assert "constant_column" in types
    assert next(f for f in findings if f.finding_type == "constant_column").severity == "info"


def test_detect_varied_column_no_constant_finding():
    col = _col(distinct_count=50, distinct_pct=50.0, row_count=100)
    findings = detect_profile_findings(_profile([col]))
    assert not any(f.finding_type == "constant_column" for f in findings)


# ── detect_profile_findings — empty string checks ────────────────────────────

def test_detect_high_empty_string_warning():
    col = _col(
        dtype="VARCHAR",
        empty_string_count=15,
        empty_string_pct=15.0,
        row_count=100,
        null_count=0,
        null_pct=0.0,
        distinct_count=50,
    )
    findings = detect_profile_findings(_profile([col]))
    types = [f.finding_type for f in findings]
    assert "high_empty_string_rate" in types
    assert (
        next(f for f in findings if f.finding_type == "high_empty_string_rate").severity
        == "warning"
    )


def test_detect_below_empty_string_threshold_no_finding():
    col = _col(
        dtype="VARCHAR",
        empty_string_count=5,
        empty_string_pct=5.0,
        row_count=100,
        null_count=0,
        null_pct=0.0,
        distinct_count=50,
    )
    findings = detect_profile_findings(_profile([col]))
    assert not any(f.finding_type == "high_empty_string_rate" for f in findings)


# ── detect_profile_findings — clean column ────────────────────────────────────

def test_detect_no_findings_on_clean_column():
    col = _col(null_count=0, null_pct=0.0, distinct_count=50, distinct_pct=50.0)
    findings = detect_profile_findings(_profile([col]))
    assert findings == []
