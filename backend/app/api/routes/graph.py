from fastapi import APIRouter, Depends

from app.adapters.base import PipelineSource
from app.api.deps import get_pipeline_source
from app.schemas.graph_schema import EdgeDetail, GraphResponse
from app.services.graph_builder import build_graph, get_execution_order

router = APIRouter()


@router.get("/", response_model=GraphResponse)
def get_graph(source: PipelineSource = Depends(get_pipeline_source)):
    jobs = source.load()
    graph = build_graph(jobs)

    try:
        order = get_execution_order(graph)
        cycle_detected = False
    except ValueError:
        order = None
        cycle_detected = True

    edges = [
        EdgeDetail(source=u, target=v, config_key=data["config_key"])
        for u, v, data in graph.edges(data=True)
    ]

    return GraphResponse(
        nodes=list(graph.nodes),
        edges=edges,
        execution_order=order,
        cycle_detected=cycle_detected,
    )
