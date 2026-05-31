from pathlib import Path

from fastapi import APIRouter, Depends

from app.adapters.csv_adapter import CsvAdapter
from app.api.deps import get_csv_path
from app.models.finding import ValidationFinding
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph

router = APIRouter()


@router.get("/", response_model=list[ValidationFinding])
def get_findings(path: Path = Depends(get_csv_path)):
    jobs = CsvAdapter(str(path)).load()
    graph = build_graph(jobs)
    return detect_findings(jobs, graph)
