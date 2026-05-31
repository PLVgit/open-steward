from pathlib import Path

from fastapi import APIRouter, Depends

from app.adapters.csv_adapter import CsvAdapter
from app.api.deps import get_csv_path
from app.schemas.graph_schema import EdgeDetail, GraphResponse
from app.services.graph_builder import build_graph, get_execution_order

router = APIRouter()


@router.get("/", response_model=GraphResponse)
def get_graph(path: Path = Depends(get_csv_path)):
    jobs = CsvAdapter(str(path)).load()
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
