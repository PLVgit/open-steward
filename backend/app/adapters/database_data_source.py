"""Aggregate-only DataSource over a real database.

Accepts either:

- a path to a **DuckDB database file** (opened read-only) — zero extra
  dependencies, or
- a ``postgres://`` / ``postgresql://`` URL, attached **read-only** through
  DuckDB's ``postgres`` extension (installed automatically on first use;
  requires network once).

Credentials never live in code or config files: ``${ENV_VAR}`` placeholders in
the connection string are expanded from the environment, and the resolved URL
is never logged or echoed. Table names are validated against a strict
``schema.table`` pattern before being quoted into queries.

All aggregate queries are inherited from DuckDbAggregateSource — only the
connection handling and table→relation mapping live here.
"""

import os
import re
from pathlib import Path

import duckdb

from app.adapters.duckdb_aggregate_source import DuckDbAggregateSource

_VALID_TABLE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)?$")
_PG_PREFIXES = ("postgres://", "postgresql://")


def _expand_env(value: str) -> str:
    """Expand ${VAR} placeholders so credentials can live in the environment."""
    return re.sub(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
        lambda m: os.environ.get(m.group(1), m.group(0)),
        value,
    )


class DatabaseDataSource(DuckDbAggregateSource):
    def __init__(self, db: str) -> None:
        target = _expand_env(db)
        if target.startswith(_PG_PREFIXES):
            self._conn = duckdb.connect()
            self._conn.execute("INSTALL postgres; LOAD postgres;")
            safe_url = target.replace("'", "''")
            self._conn.execute(f"ATTACH '{safe_url}' AS ext (TYPE postgres, READ_ONLY)")
            self._catalog = "ext"
        else:
            path = Path(target)
            if not path.is_file():
                raise FileNotFoundError(f"No database file found at '{db}'.")
            self._conn = duckdb.connect(str(path), read_only=True)
            self._catalog = None

    # ── table resolution ──────────────────────────────────────────────────────

    def _relation(self, table_name: str) -> str:
        if not _VALID_TABLE.match(table_name):
            raise ValueError(
                f"Invalid table name: {table_name!r}. "
                "Use 'schema.table' or 'table' with word characters only."
            )
        parts = [f'"{p}"' for p in table_name.split(".")]
        if self._catalog is not None:
            parts = [f'"{self._catalog}"'] + parts
        return ".".join(parts)

    def table_exists(self, table_name: str) -> bool:
        if not _VALID_TABLE.match(table_name):
            return False
        try:
            self._conn.execute(f"SELECT 1 FROM {self._relation(table_name)} LIMIT 0")
            return True
        except Exception:
            return False
