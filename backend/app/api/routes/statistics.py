from fastapi import APIRouter, Depends

from app.adapters.base import PipelineSource
from app.adapters.data_source import DataSource
from app.api.deps import get_data_source, get_pipeline_source
from app.models.job_statistics import JobStatistics
from app.services.etl_statistics import compute_job_statistics

router = APIRouter()


@router.get("/", response_model=list[JobStatistics])
def get_statistics(
    source: PipelineSource = Depends(get_pipeline_source),
    data_source: DataSource = Depends(get_data_source),
):
    return compute_job_statistics(source.load(), data_source)
