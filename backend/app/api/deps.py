import os
import re
from pathlib import Path

from fastapi import HTTPException, Query

from app.adapters.base import PipelineSource
from app.adapters.csv_adapter import CsvAdapter
from app.adapters.data_source import DataSource
from app.adapters.database_data_source import DatabaseDataSource
from app.adapters.dbt_manifest_adapter import DbtManifestAdapter
from app.adapters.local_file_data_source import LocalFileDataSource

_DEFAULT_SAMPLES_DIR = (Path(__file__).parent.parent.parent / "samples").resolve()
_DEFAULT_DATA_ROOT = (Path(__file__).parent.parent.parent / "demo_data").resolve()


def get_config_dir() -> Path:
    """Root directory for config CSVs / dbt manifests served over the API.
    Defaults to the bundled samples/; point OPEN_STEWARD_CONFIG_DIR at your own
    project to analyze it through the UI/API. Read per-request so it can be
    changed without code edits."""
    override = os.environ.get("OPEN_STEWARD_CONFIG_DIR")
    return Path(override).resolve() if override else _DEFAULT_SAMPLES_DIR


def get_data_root() -> Path:
    """Root directory for table snapshots / .duckdb files served over the API.
    Defaults to the bundled demo_data/; override with OPEN_STEWARD_DATA_DIR."""
    override = os.environ.get("OPEN_STEWARD_DATA_DIR")
    return Path(override).resolve() if override else _DEFAULT_DATA_ROOT

# A table name is "schema.table" or "table" — word characters only. This blocks
# path traversal via the table parameter, since the data source resolves the
# table name to a file path under the data directory.
_TABLE_NAME = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")


def _resolve_samples_file(name: str) -> Path:
    root = get_config_dir()
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root):
        raise HTTPException(status_code=400, detail="File path is outside the allowed config directory.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {name}")
    return resolved


def get_pipeline_source(
    file: str | None = Query(None, description="Config CSV filename inside the samples/ directory"),
    manifest: str | None = Query(None, description="dbt manifest.json filename inside the samples/ directory"),
) -> PipelineSource:
    """Pipeline definitions come from exactly one source: a config CSV
    (`file=`) or a dbt manifest (`manifest=`), both confined to samples/."""
    if (file is None) == (manifest is None):
        raise HTTPException(status_code=400, detail="Provide exactly one of 'file' or 'manifest'.")
    if file is not None:
        return CsvAdapter(str(_resolve_samples_file(file)))
    return DbtManifestAdapter(str(_resolve_samples_file(manifest)))


def _resolve_data_dir(data_dir: str) -> Path:
    """Resolve a data_dir query value to a directory confined under the data root."""
    root = get_data_root()
    resolved = (root / data_dir).resolve()
    if not resolved.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Data directory is outside the allowed data root.")
    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"Data directory not found: {data_dir}")
    return resolved


def _resolve_db_file(db: str) -> Path:
    """Resolve a db query value to a database file confined under DATA_ROOT.

    Connection URLs (credentials) are never accepted over the API — database
    URLs are a CLI concern, configured through environment variables.
    """
    if "://" in db:
        raise HTTPException(
            status_code=400,
            detail="Database URLs are not accepted over the API; use the CLI with an environment-configured URL.",
        )
    root = get_data_root()
    resolved = (root / db).resolve()
    if not resolved.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Database file is outside the allowed data root.")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"Database file not found: {db}")
    return resolved


_DATA_DIR_QUERY = Query(None, description="Directory of table snapshots, relative to demo_data/")
_DB_QUERY = Query(None, description="DuckDB database file, relative to demo_data/")


def _make_data_source(data_dir: str | None, db: str | None) -> DataSource:
    if data_dir is not None and db is not None:
        raise HTTPException(status_code=400, detail="Provide only one of 'data_dir' or 'db'.")
    if db is not None:
        return DatabaseDataSource(str(_resolve_db_file(db)))
    return LocalFileDataSource(_resolve_data_dir(data_dir if data_dir is not None else "."))


def get_data_source(
    data_dir: str | None = _DATA_DIR_QUERY,
    db: str | None = _DB_QUERY,
) -> DataSource:
    """Snapshot- or database-backed DataSource; defaults to demo_data/ snapshots."""
    return _make_data_source(data_dir, db)


def get_optional_data_source(
    data_dir: str | None = _DATA_DIR_QUERY,
    db: str | None = _DB_QUERY,
) -> DataSource | None:
    """Like get_data_source, but None when neither param is given — so callers
    can keep their non-reconciliation behavior unchanged."""
    if data_dir is None and db is None:
        return None
    return _make_data_source(data_dir, db)


def get_table_name(
    table: str = Query(..., description="Table name to profile, e.g. staging.orders"),
) -> str:
    if not _TABLE_NAME.match(table):
        raise HTTPException(
            status_code=400,
            detail="Invalid table name. Use 'schema.table' or 'table' with word characters only.",
        )
    return table
