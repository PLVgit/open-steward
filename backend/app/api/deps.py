from pathlib import Path

from fastapi import HTTPException, Query

SAMPLES_DIR = (Path(__file__).parent.parent.parent / "samples").resolve()


def get_csv_path(file: str = Query(..., description="Filename inside the samples/ directory")) -> Path:
    resolved = (SAMPLES_DIR / file).resolve()
    if not resolved.is_relative_to(SAMPLES_DIR):
        raise HTTPException(status_code=400, detail="File path is outside the allowed samples directory.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    return resolved
