from pathlib import Path

from fastapi import HTTPException, Query

SAMPLES_DIR = (Path(__file__).parent.parent.parent / "samples").resolve()
DATA_ROOT = (Path(__file__).parent.parent.parent / "demo_data").resolve()


def get_csv_path(file: str = Query(..., description="Filename inside the samples/ directory")) -> Path:
    resolved = (SAMPLES_DIR / file).resolve()
    if not resolved.is_relative_to(SAMPLES_DIR):
        raise HTTPException(status_code=400, detail="File path is outside the allowed samples directory.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    return resolved


def get_data_dir(
    data_dir: str = Query(".", description="Directory of table snapshots, relative to demo_data/"),
) -> Path:
    resolved = (DATA_ROOT / data_dir).resolve()
    if not resolved.is_relative_to(DATA_ROOT):
        raise HTTPException(status_code=400, detail="Data directory is outside the allowed data root.")
    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"Data directory not found: {data_dir}")
    return resolved
