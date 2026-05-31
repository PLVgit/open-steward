from app.models.pipeline_job import PipelineJob
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph


def make_job(**kwargs) -> PipelineJob:
    defaults = dict(
        config_key="etl_001",
        pipeline_name="Test ETL",
        enabled=True,
        source_table="raw.src",
        target_table="staging.tgt",
    )
    defaults.update(kwargs)
    return PipelineJob(**defaults)


def run(jobs: list[PipelineJob]):
    return detect_findings(jobs, build_graph(jobs))


def findings_of(jobs, finding_type):
    return [f for f in run(jobs) if f.finding_type == finding_type]


# --- clean graph ---

def test_no_findings_on_clean_graph():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_002", source_table="staging.orders", target_table="mart.orders"),
    ]
    assert run(jobs) == []


# --- circular_dependency ---

def test_detects_circular_dependency():
    jobs = [
        make_job(config_key="etl_001", source_table="A", target_table="B"),
        make_job(config_key="etl_002", source_table="B", target_table="C"),
        make_job(config_key="etl_003", source_table="C", target_table="A"),
    ]
    found = findings_of(jobs, "circular_dependency")
    assert len(found) == 1
    assert found[0].severity == "error"


# --- duplicate_target ---

def test_detects_duplicate_target():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_007", source_table="raw.orders", target_table="staging.orders"),
    ]
    found = findings_of(jobs, "duplicate_target")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert found[0].affected_table == "staging.orders"


# --- unresolved_upstream ---

def test_known_external_prefix_not_flagged():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
    ]
    assert findings_of(jobs, "unresolved_upstream") == []


def test_unresolved_upstream_flagged():
    jobs = [
        make_job(config_key="etl_001", source_table="unknown.orders", target_table="staging.orders"),
    ]
    found = findings_of(jobs, "unresolved_upstream")
    assert len(found) == 1
    assert found[0].severity == "info"
    assert found[0].affected_table == "unknown.orders"


def test_unresolved_upstream_all_prefixes_suppressed():
    jobs = [
        make_job(config_key="etl_001", source_table="source.crm", target_table="staging.crm"),
        make_job(config_key="etl_002", source_table="landing.events", target_table="staging.events"),
        make_job(config_key="etl_003", source_table="external.payments", target_table="staging.payments"),
    ]
    assert findings_of(jobs, "unresolved_upstream") == []


# --- disabled_dependency ---

def test_detects_disabled_dependency():
    jobs = [
        make_job(config_key="etl_005", source_table="raw.events", target_table="staging.events", enabled=False),
        make_job(config_key="etl_006", source_table="staging.events", target_table="mart.events", enabled=True),
    ]
    found = findings_of(jobs, "disabled_dependency")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert found[0].affected_job == "etl_006"


def test_disabled_job_not_flagged_for_disabled_dependency():
    jobs = [
        make_job(config_key="etl_005", source_table="raw.events", target_table="staging.events", enabled=False),
        make_job(config_key="etl_006", source_table="staging.events", target_table="mart.events", enabled=False),
    ]
    assert findings_of(jobs, "disabled_dependency") == []


# --- multiple findings ---

def test_multiple_findings_returned():
    jobs = [
        make_job(config_key="etl_001", source_table="A", target_table="B"),
        make_job(config_key="etl_002", source_table="B", target_table="C"),
        make_job(config_key="etl_003", source_table="C", target_table="A"),
        make_job(config_key="etl_004", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_005", source_table="raw.orders", target_table="staging.orders"),
    ]
    types = {f.finding_type for f in run(jobs)}
    assert "circular_dependency" in types
    assert "duplicate_target" in types
