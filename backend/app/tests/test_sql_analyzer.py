import pytest

from app.models.pipeline_job import PipelineJob
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph
from app.services.sql_analyzer import analyze_sql


def _job(sql: str | None = None, load_type: str | None = None, key: str = "etl_001") -> PipelineJob:
    return PipelineJob(
        config_key=key,
        pipeline_name="Test Job",
        enabled=True,
        source_table="raw.orders",
        target_table="staging.orders",
        sql_query=sql,
        load_type=load_type,
    )


# ── skip None ─────────────────────────────────────────────────────────────────

def test_none_sql_skipped():
    assert analyze_sql([_job(sql=None)]) == []


# ── select_star ───────────────────────────────────────────────────────────────

def test_select_star_warning():
    findings = analyze_sql([_job("SELECT * FROM t")])
    types = [f.finding_type for f in findings]
    assert "select_star" in types
    assert findings[types.index("select_star")].severity == "warning"


def test_count_star_not_flagged():
    findings = analyze_sql([_job("SELECT COUNT(*) FROM t")])
    assert not any(f.finding_type == "select_star" for f in findings)


def test_select_star_in_subquery_flagged():
    findings = analyze_sql([_job("SELECT id FROM (SELECT * FROM t) sub")])
    assert any(f.finding_type == "select_star" for f in findings)


# ── explicit_cast ─────────────────────────────────────────────────────────────

def test_cast_warning():
    findings = analyze_sql([_job("SELECT CAST(x AS INT) FROM t")])
    types = [f.finding_type for f in findings]
    assert "explicit_cast" in types
    assert findings[types.index("explicit_cast")].severity == "warning"


def test_try_cast_warning():
    findings = analyze_sql([_job("SELECT TRY_CAST(x AS INT) FROM t")])
    assert any(f.finding_type == "explicit_cast" for f in findings)


def test_no_cast_no_finding():
    findings = analyze_sql([_job("SELECT x FROM t WHERE id = 1")])
    assert not any(f.finding_type == "explicit_cast" for f in findings)


# ── cross_join ────────────────────────────────────────────────────────────────

def test_cross_join_error():
    findings = analyze_sql([_job("SELECT a.x FROM a CROSS JOIN b")])
    types = [f.finding_type for f in findings]
    assert "cross_join" in types
    assert findings[types.index("cross_join")].severity == "error"


def test_inner_join_not_flagged():
    findings = analyze_sql([_job("SELECT a.x FROM a INNER JOIN b ON a.id = b.id")])
    assert not any(f.finding_type == "cross_join" for f in findings)


# ── missing_filter_on_full_load ───────────────────────────────────────────────

def test_full_load_no_where_flagged():
    findings = analyze_sql([_job("SELECT x FROM t", load_type="full")])
    types = [f.finding_type for f in findings]
    assert "missing_filter_on_full_load" in types
    assert findings[types.index("missing_filter_on_full_load")].severity == "info"


def test_incremental_load_no_where_not_flagged():
    findings = analyze_sql([_job("SELECT x FROM t", load_type="incremental")])
    assert not any(f.finding_type == "missing_filter_on_full_load" for f in findings)


def test_full_load_with_limit_not_flagged():
    findings = analyze_sql([_job("SELECT x FROM t LIMIT 100", load_type="full")])
    assert not any(f.finding_type == "missing_filter_on_full_load" for f in findings)


def test_full_load_with_where_not_flagged():
    findings = analyze_sql([_job("SELECT x FROM t WHERE id > 0", load_type="full")])
    assert not any(f.finding_type == "missing_filter_on_full_load" for f in findings)


def test_none_load_type_not_flagged():
    findings = analyze_sql([_job("SELECT x FROM t", load_type=None)])
    assert not any(f.finding_type == "missing_filter_on_full_load" for f in findings)


# ── multiple findings in one query ────────────────────────────────────────────

def test_multiple_findings_one_query():
    findings = analyze_sql([_job("SELECT * FROM a CROSS JOIN b")])
    types = [f.finding_type for f in findings]
    assert "select_star" in types
    assert "cross_join" in types


# ── affected_job reference ────────────────────────────────────────────────────

def test_findings_reference_correct_job():
    findings = analyze_sql([_job("SELECT * FROM t", key="etl_042")])
    assert all(f.affected_job == "etl_042" for f in findings)


# ── unparseable SQL ───────────────────────────────────────────────────────────

def test_unparseable_sql_warning():
    findings = analyze_sql([_job("THIS IS NOT SQL @@@ !!!")])
    assert len(findings) == 1
    assert findings[0].finding_type == "unparseable_sql"
    assert findings[0].severity == "warning"


# ── integration: detect_findings includes SQL findings ────────────────────────

def test_integration_with_detect_findings():
    jobs = [_job("SELECT * FROM raw.orders")]
    graph = build_graph(jobs)
    findings = detect_findings(jobs, graph)
    assert any(f.finding_type == "select_star" for f in findings)
