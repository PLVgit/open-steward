from pathlib import Path

from fastapi import APIRouter, Depends

from app.adapters.csv_adapter import CsvAdapter
from app.adapters.local_file_data_source import LocalFileDataSource
from app.api.deps import get_csv_path, get_optional_data_dir
from app.models.finding import ValidationFinding
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph
from app.services.reconciliation_engine import reconcile_jobs

router = APIRouter()


@router.get("/", response_model=list[ValidationFinding])
def get_findings(
    path: Path = Depends(get_csv_path),
    data_dir: Path | None = Depends(get_optional_data_dir),
):
    jobs = CsvAdapter(str(path)).load()
    graph = build_graph(jobs)
    findings = detect_findings(jobs, graph)
    # Reconciliation findings require local table snapshots; only included when
    # a data_dir is supplied. Without it, behavior is unchanged (structural + SQL).
    if data_dir is not None:
        findings = findings + reconcile_jobs(jobs, LocalFileDataSource(data_dir))
    return findings
