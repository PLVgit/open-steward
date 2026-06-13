"""Conservative extraction of simple two-table joins.

Given a job's SQL, decide whether it is a simple two-table INNER/LEFT join with
a single equality ON condition (and an optional left-only WHERE), and if so
return the join shape. Anything more complex returns None and the caller falls
back safely — no misleading join findings are produced.

This builds on the transformation-aware direction of filter_analyzer: Ticket 21
explains row changes from a simple WHERE, Ticket 22 explains row changes from a
simple JOIN (optionally after such a WHERE).
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from app.services.filter_analyzer import _is_simple_predicate


@dataclass(frozen=True)
class JoinInfo:
    join_type: str  # "INNER" or "LEFT"
    left_table: str
    right_table: str
    left_key: str
    right_key: str
    where_clause: str | None  # bare-column predicate over the left table, or None


def extract_simple_join(sql: str | None) -> JoinInfo | None:
    if not sql or not sql.strip():
        return None
    try:
        parsed = sqlglot.parse_one(sql)
    except Exception:
        return None

    if not isinstance(parsed, exp.Select):
        return None
    # Same structural conservatism as the filter analyzer.
    if (
        parsed.find(exp.With) is not None
        or parsed.find(exp.Group) is not None
        or parsed.find(exp.Having) is not None
    ):
        return None
    if parsed.args.get("distinct") or parsed.args.get("limit") is not None:
        return None
    if parsed.find(exp.AggFunc) is not None or parsed.find(exp.Window) is not None:
        return None

    joins = list(parsed.find_all(exp.Join))
    if len(joins) != 1:
        return None
    join = joins[0]

    join_type = _classify_join(join)
    if join_type is None:
        return None

    from_exp = parsed.find(exp.From)
    if from_exp is None:
        return None
    left_table_node = from_exp.find(exp.Table)
    right_table_node = join.find(exp.Table)
    if left_table_node is None or right_table_node is None:
        return None
    # Reject subqueries on either side.
    if from_exp.find(exp.Subquery) is not None or join.find(exp.Subquery) is not None:
        return None

    # Build an alias/name -> logical-table map to resolve column qualifiers.
    alias_map: dict[str, str] = {}
    left_name = _table_name(left_table_node)
    right_name = _table_name(right_table_node)
    _register(alias_map, left_table_node, left_name)
    _register(alias_map, right_table_node, right_name)
    if left_name.lower() == right_name.lower():
        return None  # self-join: ambiguous for this conservative analysis

    on = join.args.get("on")
    keys = _equality_keys(on, alias_map, left_name, right_name)
    if keys is None:
        return None
    left_key, right_key = keys

    where_clause = _left_only_where(parsed, alias_map, left_name)
    if where_clause is _UNSAFE:
        return None

    return JoinInfo(
        join_type=join_type,
        left_table=left_name,
        right_table=right_name,
        left_key=left_key,
        right_key=right_key,
        where_clause=where_clause,
    )


# Sentinel: a WHERE exists but cannot be safely assigned to the left table.
_UNSAFE = object()


def _classify_join(join: exp.Join) -> str | None:
    side = (join.args.get("side") or "").upper()
    kind = (join.args.get("kind") or "").upper()
    if kind == "CROSS" or join.args.get("using"):
        return None
    if join.args.get("on") is None:
        return None  # NATURAL / CROSS / comma joins have no ON
    if side == "LEFT":
        return "LEFT"
    if side in ("RIGHT", "FULL"):
        return None
    if side == "":
        # plain JOIN or INNER JOIN
        return "INNER" if kind in ("", "INNER") else None
    return None


def _table_name(table: exp.Table) -> str:
    return ".".join(part for part in (table.db, table.name) if part)


def _register(alias_map: dict[str, str], table: exp.Table, logical: str) -> None:
    alias = table.alias_or_name  # alias if present, else the table name
    if alias:
        alias_map[alias.lower()] = logical
    alias_map[table.name.lower()] = logical


def _equality_keys(
    on: exp.Expression | None,
    alias_map: dict[str, str],
    left_name: str,
    right_name: str,
) -> tuple[str, str] | None:
    if not isinstance(on, exp.EQ):
        return None
    left_col, right_col = on.left, on.right
    if not isinstance(left_col, exp.Column) or not isinstance(right_col, exp.Column):
        return None

    a_side = _resolve_side(left_col, alias_map, left_name, right_name)
    b_side = _resolve_side(right_col, alias_map, left_name, right_name)
    if a_side is None or b_side is None or a_side == b_side:
        return None

    if a_side == "left":
        return left_col.name, right_col.name
    return right_col.name, left_col.name


def _resolve_side(
    col: exp.Column, alias_map: dict[str, str], left_name: str, right_name: str
) -> str | None:
    qualifier = col.table
    if not qualifier:
        return None  # unqualified -> ambiguous
    logical = alias_map.get(qualifier.lower())
    if logical is None:
        return None
    if logical.lower() == left_name.lower():
        return "left"
    if logical.lower() == right_name.lower():
        return "right"
    return None


def _left_only_where(
    parsed: exp.Select, alias_map: dict[str, str], left_name: str
):
    where = parsed.find(exp.Where)
    if where is None:
        return None
    predicate = where.this
    if predicate.find(exp.Select) is not None:
        return _UNSAFE
    if not _is_simple_predicate(predicate):
        return _UNSAFE
    # Every column must qualify to the left table.
    for col in predicate.find_all(exp.Column):
        qualifier = col.table
        if not qualifier or alias_map.get(qualifier.lower(), "").lower() != left_name.lower():
            return _UNSAFE
    # Strip qualifiers so the predicate runs against the left table directly.
    stripped = predicate.copy()
    for col in stripped.find_all(exp.Column):
        col.set("table", None)
        col.set("db", None)
        col.set("catalog", None)
    return stripped.sql()
