from pathlib import Path

from app.adapters.csv_adapter import CsvAdapter
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph, detect_cycles, get_execution_order

_SAMPLES = Path(__file__).parent.parent.parent / "samples"
_SAMPLE_CSV = str(_SAMPLES / "sample_config.csv")
_CYCLE_CSV = str(_SAMPLES / "cycle_config.csv")


def _load_sample():
    jobs = CsvAdapter(_SAMPLE_CSV).load()
    graph = build_graph(jobs)
    findings = detect_findings(jobs, graph)
    return jobs, graph, findings


def test_sample_job_count():
    jobs, _, _ = _load_sample()
    assert len(jobs) == 7


def test_sample_enabled_job_count():
    jobs, _, _ = _load_sample()
    assert sum(1 for j in jobs if j.enabled) == 6


def test_sample_no_circular_dependency():
    _, _, findings = _load_sample()
    assert not any(f.finding_type == "circular_dependency" for f in findings)


def test_sample_duplicate_target_finding():
    _, _, findings = _load_sample()
    dups = [f for f in findings if f.finding_type == "duplicate_target"]
    assert len(dups) == 1
    assert dups[0].severity == "error"
    assert dups[0].affected_table == "staging.orders"


def test_sample_disabled_dependency_finding():
    _, _, findings = _load_sample()
    disabled = [f for f in findings if f.finding_type == "disabled_dependency"]
    assert len(disabled) == 1
    assert disabled[0].severity == "error"
    assert disabled[0].affected_job == "etl_006"


def test_sample_no_unresolved_upstream():
    _, _, findings = _load_sample()
    assert not any(f.finding_type == "unresolved_upstream" for f in findings)


def test_sample_execution_order_is_valid():
    _, graph, _ = _load_sample()
    order = get_execution_order(graph)
    assert isinstance(order, list)
    assert len(order) > 0


def test_cycle_config_detected():
    jobs = CsvAdapter(_CYCLE_CSV).load()
    graph = build_graph(jobs)
    cycles = detect_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"table_a", "table_b", "table_c"}
