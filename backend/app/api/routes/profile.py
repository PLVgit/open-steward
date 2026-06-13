from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.local_file_data_source import LocalFileDataSource
from app.api.deps import get_data_dir, get_table_name
from app.schemas.profile_schema import ProfileResponse
from app.services.dq_profiler import detect_profile_findings, profile_table

router = APIRouter()


@router.get("/", response_model=ProfileResponse)
def get_profile(
    table: str = Depends(get_table_name),
    data_dir: Path = Depends(get_data_dir),
):
    ds = LocalFileDataSource(data_dir)
    try:
        profile = profile_table(table, ds)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    findings = detect_profile_findings(profile)
    return ProfileResponse(profile=profile, findings=findings)
