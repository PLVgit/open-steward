from fastapi import APIRouter, Depends, Query

from app.adapters.base import PipelineSource
from app.adapters.data_source import DataSource
from app.api.deps import get_optional_data_source, get_pipeline_source
from app.models.finding import ValidationFinding
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph
from app.services.reconciliation_engine import reconcile_jobs

router = APIRouter()


@router.get("/", response_model=list[ValidationFinding])
def get_findings(
    source: PipelineSource = Depends(get_pipeline_source),
    data_source: DataSource | None = Depends(get_optional_data_source),
    row_loss_tolerance: float = Query(
        0.0, ge=0.0, le=100.0,
        description="Suppress row-loss warnings at or below this loss percentage (default 0 = strict).",
    ),
):
    jobs = source.load()
    graph = build_graph(jobs)
    findings = detect_findings(jobs, graph)
    # Reconciliation findings require table data (snapshots or a database);
    # only included when a data_dir/db is supplied. Without it, behavior is
    # unchanged (structural + SQL findings only).
    if data_source is not None:
        findings = findings + reconcile_jobs(
            jobs, data_source, row_loss_tolerance_pct=row_loss_tolerance
        )
    return findings
