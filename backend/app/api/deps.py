import re
from pathlib import Path

from fastapi import HTTPException, Query

SAMPLES_DIR = (Path(__file__).parent.parent.parent / "samples").resolve()
DATA_ROOT = (Path(__file__).parent.parent.parent / "demo_data").resolve()

# A table name is "schema.table" or "table" — word characters only. This blocks
# path traversal via the table parameter, since the data source resolves the
# table name to a file path under the data directory.
_TABLE_NAME = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")


def get_csv_path(file: str = Query(..., description="Filename inside the samples/ directory")) -> Path:
    resolved = (SAMPLES_DIR / file).resolve()
    if not resolved.is_relative_to(SAMPLES_DIR):
        raise HTTPException(status_code=400, detail="File path is outside the allowed samples directory.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    return resolved


def _resolve_data_dir(data_dir: str) -> Path:
    """Resolve a data_dir query value to a directory confined under DATA_ROOT."""
    resolved = (DATA_ROOT / data_dir).resolve()
    if not resolved.is_relative_to(DATA_ROOT):
        raise HTTPException(status_code=400, detail="Data directory is outside the allowed data root.")
    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"Data directory not found: {data_dir}")
    return resolved


def get_data_dir(
    data_dir: str = Query(".", description="Directory of table snapshots, relative to demo_data/"),
) -> Path:
    return _resolve_data_dir(data_dir)


def get_optional_data_dir(
    data_dir: str | None = Query(
        None, description="Optional directory of table snapshots, relative to demo_data/"
    ),
) -> Path | None:
    """Like get_data_dir, but optional. Returns None when the param is absent so
    callers can keep their non-reconciliation behavior unchanged."""
    if data_dir is None:
        return None
    return _resolve_data_dir(data_dir)


def get_table_name(
    table: str = Query(..., description="Table name to profile, e.g. staging.orders"),
) -> str:
    if not _TABLE_NAME.match(table):
        raise HTTPException(
            status_code=400,
            detail="Invalid table name. Use 'schema.table' or 'table' with word characters only.",
        )
    return table
