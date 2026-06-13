from pathlib import Path

from fastapi import APIRouter, Depends

from app.adapters.csv_adapter import CsvAdapter
from app.adapters.local_file_data_source import LocalFileDataSource
from app.api.deps import get_csv_path, get_data_dir
from app.models.job_statistics import JobStatistics
from app.services.etl_statistics import compute_job_statistics

router = APIRouter()


@router.get("/", response_model=list[JobStatistics])
def get_statistics(
    path: Path = Depends(get_csv_path),
    data_dir: Path = Depends(get_data_dir),
):
    jobs = CsvAdapter(str(path)).load()
    return compute_job_statistics(jobs, LocalFileDataSource(data_dir))
