"""Shared aggregate-only query implementation over a DuckDB connection.

Every concrete DataSource in Open Steward runs the same scalar aggregate SQL —
what differs is only *where the table lives* (a local CSV/Parquet file, a
DuckDB database, an attached external database). Subclasses provide:

- ``_relation(table_name)`` — a SQL fragment the table can be selected from
- ``table_exists(table_name)``

and inherit every aggregate method. No method ever returns raw rows: counts,
distinct counts, null counts, filtered counts and join-output counts only.
"""

import re

import duckdb

from app.models.column_info import ColumnInfo

_VALID_COLUMN = re.compile(r"^[A-Za-z0-9_]+$")


class DuckDbAggregateSource:
    _conn: duckdb.DuckDBPyConnection

    # ── subclass interface ────────────────────────────────────────────────────

    def _relation(self, table_name: str) -> str:
        """A SQL fragment for FROM clauses (file reader call or quoted name)."""
        raise NotImplementedError

    def table_exists(self, table_name: str) -> bool:
        raise NotImplementedError

    # ── shared helpers ────────────────────────────────────────────────────────

    def _require_column(self, table_name: str, column: str) -> str:
        """Validate column name syntax and existence. Returns the quoted identifier."""
        if not _VALID_COLUMN.match(column):
            raise ValueError(f"Invalid column name: {column!r}")
        rows = self._conn.execute(
            f"DESCRIBE SELECT * FROM {self._relation(table_name)}"
        ).fetchall()
        name_map = {row[0].lower(): row[0] for row in rows}
        actual = name_map.get(column.lower())
        if actual is None:
            raise ValueError(f"Column '{column}' does not exist in the table.")
        return f'"{actual}"'

    def _left_subquery(self, left_table: str, where_clause: str | None) -> str:
        rel = self._relation(left_table)
        if where_clause:
            return f"(SELECT * FROM {rel} WHERE {where_clause})"
        return f"(SELECT * FROM {rel})"

    # ── aggregate interface ───────────────────────────────────────────────────

    def get_schema(self, table_name: str) -> list[ColumnInfo]:
        rows = self._conn.execute(
            f"DESCRIBE SELECT * FROM {self._relation(table_name)}"
        ).fetchall()
        return [ColumnInfo(name=row[0], dtype=row[1]) for row in rows]

    def get_row_count(self, table_name: str) -> int:
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._relation(table_name)}"
        ).fetchone()[0]

    def get_distinct_count(self, table_name: str, column: str) -> int:
        col = self._require_column(table_name, column)
        return self._conn.execute(
            f"SELECT COUNT(DISTINCT {col}) FROM {self._relation(table_name)}"
        ).fetchone()[0]

    def get_null_count(self, table_name: str, column: str) -> int:
        col = self._require_column(table_name, column)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._relation(table_name)} WHERE {col} IS NULL"
        ).fetchone()[0]

    def get_empty_string_count(self, table_name: str, column: str) -> int:
        col = self._require_column(table_name, column)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._relation(table_name)} WHERE {col} = ''"
        ).fetchone()[0]

    def get_filtered_row_count(self, table_name: str, where_clause: str) -> int:
        """Count rows matching a WHERE predicate. The predicate is a SQL
        fragment rendered by filter_analyzer (qualifiers stripped); callers
        catch exceptions and fall back when it cannot be evaluated."""
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {self._relation(table_name)} WHERE {where_clause}"
        ).fetchone()[0]

    def get_unmatched_left_count(
        self,
        left_table: str,
        left_key: str,
        right_table: str,
        right_key: str,
        where_clause: str | None = None,
    ) -> int:
        """Count left rows (after an optional WHERE) with no matching right key.
        A scalar anti-join count — no join output is materialized."""
        lkey = self._require_column(left_table, left_key)
        rkey = self._require_column(right_table, right_key)
        left_sub = self._left_subquery(left_table, where_clause)
        right_rel = self._relation(right_table)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {left_sub} l "
            f"WHERE NOT EXISTS (SELECT 1 FROM {right_rel} r WHERE r.{rkey} = l.{lkey})"
        ).fetchone()[0]

    def get_join_output_row_count(
        self,
        left_table: str,
        left_key: str,
        right_table: str,
        right_key: str,
        join_type: str,
        where_clause: str | None = None,
    ) -> int:
        """Count the rows a simple INNER/LEFT join would produce (after an
        optional left WHERE). Returns only the scalar count — no rows are
        returned and the join result is never materialized for the caller."""
        lkey = self._require_column(left_table, left_key)
        rkey = self._require_column(right_table, right_key)
        join_kw = "LEFT JOIN" if join_type.upper() == "LEFT" else "JOIN"
        left_sub = self._left_subquery(left_table, where_clause)
        right_rel = self._relation(right_table)
        return self._conn.execute(
            f"SELECT COUNT(*) FROM {left_sub} l "
            f"{join_kw} {right_rel} r ON l.{lkey} = r.{rkey}"
        ).fetchone()[0]

    def get_duplicate_key_count(self, table_name: str, primary_key: str) -> int:
        col = self._require_column(table_name, primary_key)
        return self._conn.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT {col}, COUNT(*) AS cnt
                FROM {self._relation(table_name)}
                GROUP BY {col}
                HAVING cnt > 1
            )
            """
        ).fetchone()[0]
