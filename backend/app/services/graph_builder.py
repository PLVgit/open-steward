import networkx as nx

from app.models.pipeline_job import PipelineJob


def build_graph(jobs: list[PipelineJob]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for job in jobs:
        graph.add_node(job.source_table)
        graph.add_node(job.target_table)
        graph.add_edge(job.source_table, job.target_table, config_key=job.config_key)
        # Additional upstream dependencies (e.g. multi-parent dbt models) each
        # contribute an edge into the target. source_table stays the primary
        # edge, so CSV configs (empty depends_on) are unaffected.
        for dep in job.depends_on:
            if dep != job.source_table:
                graph.add_edge(dep, job.target_table, config_key=job.config_key)
    return graph


def get_execution_order(graph: nx.DiGraph) -> list[str]:
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(
            "Pipeline graph contains a circular dependency; cannot determine execution order."
        )
    return list(nx.topological_sort(graph))


def detect_cycles(graph: nx.DiGraph) -> list[list[str]]:
    return list(nx.simple_cycles(graph))
