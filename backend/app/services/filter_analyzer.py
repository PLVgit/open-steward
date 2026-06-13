"""Conservative extraction of simple single-source WHERE filters.

Given a job's SQL, decide whether its row count can be explained by a plain
WHERE filter applied to a single source table, and if so return the WHERE
predicate as a SQL fragment (with table qualifiers stripped) suitable for
counting matching source rows.

The extractor is deliberately strict: anything it cannot prove to be a simple
single-source filter returns None, and the caller falls back to existing
behavior. In particular, ANY join is rejected — joins can legitimately change
row counts (unmatched rows, fan-out, duplicate keys) and belong to the future
join-aware advisory statistics work, not here.
"""

import sqlglot
from sqlglot import exp

# Comparison operators allowed in a simple predicate.
_COMPARISONS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE)
# Literal-like operands allowed on the non-column side of a comparison / IN.
_LITERALS = (exp.Literal, exp.Boolean, exp.Null)


def extract_simple_filter(sql: str | None, source_table: str) -> str | None:
    """Return the rendered WHERE predicate if `sql` is a simple single-source
    filter over `source_table`, else None."""
    if not sql or not sql.strip():
        return None

    try:
        parsed = sqlglot.parse_one(sql)
    except Exception:
        return None

    if not _is_plain_single_select(parsed, source_table):
        return None

    where = parsed.find(exp.Where)
    if where is None:
        return None
    predicate = where.this

    # Reject subqueries inside the WHERE (e.g. IN (SELECT ...)).
    if predicate.find(exp.Select) is not None:
        return None
    if not _is_simple_predicate(predicate):
        return None

    # Strip single-table qualifiers (o.status -> status) so the predicate runs
    # directly against the source file.
    stripped = predicate.copy()
    for col in stripped.find_all(exp.Column):
        col.set("table", None)
        col.set("db", None)
        col.set("catalog", None)
    return stripped.sql()


def _is_plain_single_select(parsed: exp.Expression, source_table: str) -> bool:
    # Set operations (UNION/INTERSECT/EXCEPT) are not plain SELECTs.
    if not isinstance(parsed, exp.Select):
        return False
    # Reject CTEs, GROUP BY, HAVING. (Found rather than keyed, to be robust to
    # sqlglot arg-name differences across versions.)
    if (
        parsed.find(exp.With) is not None
        or parsed.find(exp.Group) is not None
        or parsed.find(exp.Having) is not None
    ):
        return False
    # DISTINCT / LIMIT live directly on the SELECT.
    if parsed.args.get("distinct") or parsed.args.get("limit") is not None:
        return False
    # Reject any join.
    if parsed.find(exp.Join) is not None:
        return False
    # Reject aggregate and window functions anywhere.
    if parsed.find(exp.AggFunc) is not None or parsed.find(exp.Window) is not None:
        return False

    from_exp = parsed.find(exp.From)
    if from_exp is None:
        return False
    # Reject subqueries in FROM.
    if from_exp.find(exp.Subquery) is not None:
        return False
    tables = list(from_exp.find_all(exp.Table))
    if len(tables) != 1:
        return False
    table = tables[0]
    name = ".".join(part for part in (table.db, table.name) if part)
    return name.lower() == source_table.lower()


def _is_simple_predicate(node: exp.Expression) -> bool:
    """True only for AND/OR combinations of the explicitly allowed simple
    predicate forms."""
    if isinstance(node, exp.Paren):
        return _is_simple_predicate(node.this)
    if isinstance(node, (exp.And, exp.Or)):
        return _is_simple_predicate(node.left) and _is_simple_predicate(node.right)
    # IS NOT NULL -> Not(Is(col, Null))
    if isinstance(node, exp.Not):
        return isinstance(node.this, exp.Is) and _is_simple_predicate(node.this)
    # IS NULL
    if isinstance(node, exp.Is):
        return isinstance(node.this, exp.Column) and isinstance(node.expression, exp.Null)
    # column IN (literal, literal, ...)
    if isinstance(node, exp.In):
        if node.args.get("query") is not None:
            return False
        items = node.args.get("expressions") or []
        if not items:
            return False
        return isinstance(node.this, exp.Column) and all(
            isinstance(item, _LITERALS) for item in items
        )
    # column <op> literal   (or literal <op> column)
    if isinstance(node, _COMPARISONS):
        left, right = node.left, node.right
        return (
            (isinstance(left, exp.Column) and isinstance(right, _LITERALS))
            or (isinstance(left, _LITERALS) and isinstance(right, exp.Column))
        )
    return False
