from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.csv_adapter import CsvAdapter
from app.api.deps import get_csv_path
from app.models.pipeline_job import PipelineJob

router = APIRouter()


@router.get("/", response_model=list[PipelineJob])
def list_pipelines(path: Path = Depends(get_csv_path)):
    return CsvAdapter(str(path)).load()


@router.get("/{config_key}", response_model=PipelineJob)
def get_pipeline(config_key: str, path: Path = Depends(get_csv_path)):
    jobs = CsvAdapter(str(path)).load()
    for job in jobs:
        if job.config_key == config_key:
            return job
    raise HTTPException(status_code=404, detail=f"Pipeline '{config_key}' not found.")
