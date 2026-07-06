import pytest

from app.models.pipeline_job import PipelineJob
from app.services.graph_builder import build_graph, detect_cycles, get_execution_order


def make_job(**kwargs) -> PipelineJob:
    defaults = dict(
        config_key="etl_001",
        pipeline_name="Test ETL",
        enabled=True,
        source_table="src",
        target_table="tgt",
    )
    defaults.update(kwargs)
    return PipelineJob(**defaults)


def test_build_graph_nodes_and_edges():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_002", source_table="staging.orders", target_table="mart.orders"),
    ]
    graph = build_graph(jobs)
    assert set(graph.nodes) == {"raw.orders", "staging.orders", "mart.orders"}
    assert graph.has_edge("raw.orders", "staging.orders")
    assert graph.has_edge("staging.orders", "mart.orders")


def test_graph_edge_carries_job_key():
    jobs = [make_job(config_key="etl_001", source_table="src", target_table="tgt")]
    graph = build_graph(jobs)
    assert graph["src"]["tgt"]["config_key"] == "etl_001"


def test_execution_order_linear_chain():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_002", source_table="staging.orders", target_table="mart.orders"),
    ]
    order = get_execution_order(build_graph(jobs))
    assert order.index("raw.orders") < order.index("staging.orders")
    assert order.index("staging.orders") < order.index("mart.orders")


def test_execution_order_parallel_branches():
    jobs = [
        make_job(config_key="etl_001", source_table="raw.orders", target_table="staging.orders"),
        make_job(config_key="etl_002", source_table="raw.customers", target_table="staging.customers"),
    ]
    order = get_execution_order(build_graph(jobs))
    assert order.index("raw.orders") < order.index("staging.orders")
    assert order.index("raw.customers") < order.index("staging.customers")


def test_execution_order_raises_on_cycle():
    jobs = [
        make_job(config_key="etl_001", source_table="A", target_table="B"),
        make_job(config_key="etl_002", source_table="B", target_table="C"),
        make_job(config_key="etl_003", source_table="C", target_table="A"),
    ]
    with pytest.raises(ValueError, match="circular"):
        get_execution_order(build_graph(jobs))


def test_detect_cycles_empty_on_clean_graph():
    jobs = [
        make_job(config_key="etl_001", source_table="A", target_table="B"),
        make_job(config_key="etl_002", source_table="B", target_table="C"),
    ]
    assert detect_cycles(build_graph(jobs)) == []


def test_detect_cycles_returns_cycle():
    jobs = [
        make_job(config_key="etl_001", source_table="A", target_table="B"),
        make_job(config_key="etl_002", source_table="B", target_table="C"),
        make_job(config_key="etl_003", source_table="C", target_table="A"),
    ]
    cycles = detect_cycles(build_graph(jobs))
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_disabled_jobs_included_in_graph():
    jobs = [
        make_job(
            config_key="etl_001",
            source_table="raw.orders",
            target_table="staging.orders",
            enabled=False,
        )
    ]
    graph = build_graph(jobs)
    assert "raw.orders" in graph.nodes
    assert "staging.orders" in graph.nodes
    assert graph.has_edge("raw.orders", "staging.orders")


# ── multi-parent dependencies (depends_on) ────────────────────────────────────

def test_depends_on_adds_extra_edges():
    jobs = [make_job(
        config_key="etl_join",
        source_table="staging.orders",
        target_table="mart.enriched",
        depends_on=["staging.orders", "staging.customers"],
    )]
    graph = build_graph(jobs)
    assert graph.has_edge("staging.orders", "mart.enriched")
    assert graph.has_edge("staging.customers", "mart.enriched")
    assert graph["staging.customers"]["mart.enriched"]["config_key"] == "etl_join"


def test_depends_on_duplicate_of_source_table_not_doubled():
    jobs = [make_job(
        source_table="src", target_table="tgt", depends_on=["src"],
    )]
    graph = build_graph(jobs)
    assert graph.number_of_edges() == 1


def test_execution_order_respects_depends_on():
    jobs = [
        make_job(config_key="a", source_table="raw.x", target_table="staging.x"),
        make_job(config_key="b", source_table="raw.y", target_table="staging.y"),
        make_job(
            config_key="c",
            source_table="staging.x",
            target_table="mart.z",
            depends_on=["staging.x", "staging.y"],
        ),
    ]
    order = get_execution_order(build_graph(jobs))
    assert order.index("staging.x") < order.index("mart.z")
    assert order.index("staging.y") < order.index("mart.z")


def test_empty_depends_on_is_backward_compatible():
    jobs = [make_job(source_table="src", target_table="tgt")]
    graph = build_graph(jobs)
    assert set(graph.nodes) == {"src", "tgt"}
    assert graph.number_of_edges() == 1
