import re
from pathlib import Path

import duckdb

from app.models.column_info import ColumnInfo


class LocalFileDataSource:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._conn = duckdb.connect()

    # ── private helpers ───────────────────────────────────────────────────────

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

    def _from_clause(self, path: Path) -> str:
        safe = path.as_posix().replace("'", "''")
        if path.suffix == ".parquet":
            return f"read_parquet('{safe}')"
        # allow_quoted_nulls=false: CSV "" is an empty string, not NULL.
        # Unquoted empty fields remain NULL. This makes get_null_count and
        # get_empty_string_count correctly distinct.
        return f"read_csv_auto('{safe}', allow_quoted_nulls=false)"

    def _require_column(self, path: Path, column: str) -> str:
        """Validate column name syntax and existence. Returns the quoted identifier."""
        if not re.match(r"^[A-Za-z0-9_]+$", column):
            raise ValueError(f"Invalid column name: {column!r}")
        rows = self._conn.execute(
            f"DESCRIBE SELECT * FROM {self._from_clause(path)}"
        ).fetchall()
        name_map = {row[0].lower(): row[0] for row in rows}
        actual = name_map.get(column.lower())
        if actual is None:
            raise ValueError(f"Column '{column}' does not exist in the table.")
        return f'"{actual}"'

    # ── public interface ──────────────────────────────────────────────────────

    def table_exists(self, table_name: str) -> bool:
        return self._resolve(table_name) is not None

    def get_schema(self, table_name: str) -> list[ColumnInfo]:
        path = self._require_path(table_name)
        rows = self._conn.execute(
            f"DESCRIBE SELECT * FROM {self._from_clause(path)}"
        ).fetchall()
        return [ColumnInfo(name=row[0], dtype=row[1]) for row in rows]

    def get_row_count(self, table_name: str) -> int:
        path = self._require_path(table_name)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._from_clause(path)}"
        ).fetchone()[0]

    def get_distinct_count(self, table_name: str, column: str) -> int:
        path = self._require_path(table_name)
        col = self._require_column(path, column)
        return self._conn.execute(
            f"SELECT COUNT(DISTINCT {col}) FROM {self._from_clause(path)}"
        ).fetchone()[0]

    def get_null_count(self, table_name: str, column: str) -> int:
        path = self._require_path(table_name)
        col = self._require_column(path, column)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._from_clause(path)} WHERE {col} IS NULL"
        ).fetchone()[0]

    def get_empty_string_count(self, table_name: str, column: str) -> int:
        path = self._require_path(table_name)
        col = self._require_column(path, column)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._from_clause(path)} WHERE {col} = ''"
        ).fetchone()[0]

    def get_duplicate_key_count(self, table_name: str, primary_key: str) -> int:
        path = self._require_path(table_name)
        col = self._require_column(path, primary_key)
        fc = self._from_clause(path)
        return self._conn.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT {col}, COUNT(*) AS cnt
                FROM {fc}
                GROUP BY {col}
                HAVING cnt > 1
            )
            """
        ).fetchone()[0]
