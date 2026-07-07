from pathlib import Path

import duckdb

from app.adapters.duckdb_aggregate_source import DuckDbAggregateSource


class LocalFileDataSource(DuckDbAggregateSource):
    """Aggregate-only DataSource over local CSV/Parquet snapshots.

    A table named `schema.table` resolves to `<data_dir>/schema/table.parquet`
    (preferred) or `.csv`. All aggregate queries are inherited from
    DuckDbAggregateSource — only the table→relation resolution lives here.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._conn = duckdb.connect()

    # ── table resolution ──────────────────────────────────────────────────────

    def _resolve(self, table_name: str) -> Path | None:
        parts = table_name.lower().split(".", maxsplit=1)
        base = (
            self._data_dir / parts[0] / parts[1]
            if len(parts) == 2
            else self._data_dir / parts[0]
        )
        for ext in (".parquet", ".csv"):
            candidate = base.with_suffix(ext)
            if candidate.exists():
                return candidate
        return None

    def _require_path(self, table_name: str) -> Path:
        path = self._resolve(table_name)
        if path is None:
            raise FileNotFoundError(f"No file found for table '{table_name}'.")
        return path

    def _relation(self, table_name: str) -> str:
        path = self._require_path(table_name)
        safe = path.as_posix().replace("'", "''")
        if path.suffix == ".parquet":
            return f"read_parquet('{safe}')"
        # allow_quoted_nulls=false: CSV "" is an empty string, not NULL.
        # Unquoted empty fields remain NULL. This makes get_null_count and
        # get_empty_string_count correctly distinct.
        return f"read_csv_auto('{safe}', allow_quoted_nulls=false)"

    def table_exists(self, table_name: str) -> bool:
        return self._resolve(table_name) is not None

    def list_tables(self) -> list[str]:
        """All resolvable tables: `<file>` at the root and `<dir>.<file>` one
        level deep, for .csv/.parquet files. Sorted, de-duplicated."""
        if not self._data_dir.is_dir():
            return []
        tables: set[str] = set()
        for entry in self._data_dir.iterdir():
            if entry.is_file() and entry.suffix in (".csv", ".parquet"):
                tables.add(entry.stem)
            elif entry.is_dir():
                for child in entry.iterdir():
                    if child.is_file() and child.suffix in (".csv", ".parquet"):
                        tables.add(f"{entry.name}.{child.stem}")
        return sorted(tables)
