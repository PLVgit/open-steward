from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.data_source import DataSource
from app.api.deps import get_data_source, get_table_name
from app.schemas.profile_schema import ProfileResponse
from app.services.dq_profiler import detect_profile_findings, profile_table

router = APIRouter()


@router.get("/", response_model=ProfileResponse)
def get_profile(
    table: str = Depends(get_table_name),
    data_source: DataSource = Depends(get_data_source),
    null_threshold: float = Query(
        20.0, ge=0.0, le=100.0,
        description="Flag columns whose null rate is at or above this percentage.",
    ),
    empty_threshold: float = Query(
        10.0, ge=0.0, le=100.0,
        description="Flag text columns whose empty-string rate is at or above this percentage.",
    ),
):
    try:
        profile = profile_table(table, data_source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    findings = detect_profile_findings(
        profile,
        null_rate_threshold_pct=null_threshold,
        empty_string_threshold_pct=empty_threshold,
    )
    return ProfileResponse(profile=profile, findings=findings)
