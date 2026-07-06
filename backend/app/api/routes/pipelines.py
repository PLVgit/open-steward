from fastapi import APIRouter, Depends, HTTPException

from app.adapters.base import PipelineSource
from app.api.deps import get_pipeline_source
from app.models.pipeline_job import PipelineJob

router = APIRouter()


@router.get("/", response_model=list[PipelineJob])
def list_pipelines(source: PipelineSource = Depends(get_pipeline_source)):
    return source.load()


@router.get("/{config_key}", response_model=PipelineJob)
def get_pipeline(config_key: str, source: PipelineSource = Depends(get_pipeline_source)):
    for job in source.load():
        if job.config_key == config_key:
            return job
    raise HTTPException(status_code=404, detail=f"Pipeline '{config_key}' not found.")
