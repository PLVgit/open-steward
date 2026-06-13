from app.services.filter_analyzer import extract_simple_filter

SRC = "raw.orders"


# ── supported simple filters ────────────────────────────────────────────────

def test_simple_equality_returns_predicate():
    sql = "SELECT * FROM raw.orders WHERE status = 'completed'"
    assert extract_simple_filter(sql, SRC) == "status = 'completed'"


def test_strips_table_qualifier():
    sql = "SELECT o.id FROM raw.orders o WHERE o.status = 'completed'"
    assert extract_simple_filter(sql, SRC) == "status = 'completed'"


def test_comparison_operators_supported():
    for op in ("=", "<>", ">", ">=", "<", "<="):
        sql = f"SELECT * FROM raw.orders WHERE amount {op} 100"
        assert extract_simple_filter(sql, SRC) is not None, op


def test_in_list_supported():
    sql = "SELECT * FROM raw.orders WHERE status IN ('a', 'b', 'c')"
    assert extract_simple_filter(sql, SRC) is not None


def test_is_null_and_is_not_null_supported():
    assert extract_simple_filter("SELECT * FROM raw.orders WHERE coupon IS NULL", SRC) is not None
    assert extract_simple_filter("SELECT * FROM raw.orders WHERE coupon IS NOT NULL", SRC) is not None


def test_and_or_combination_supported():
    sql = "SELECT * FROM raw.orders WHERE status = 'completed' AND (amount > 10 OR amount < 1)"
    assert extract_simple_filter(sql, SRC) is not None


# ── rejected: joins ──────────────────────────────────────────────────────────

def test_inner_join_rejected():
    sql = (
        "SELECT o.id FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "WHERE o.status = 'completed'"
    )
    assert extract_simple_filter(sql, SRC) is None


def test_left_join_rejected():
    sql = (
        "SELECT o.id FROM raw.orders o LEFT JOIN raw.customers c ON o.cid = c.id "
        "WHERE o.status = 'completed'"
    )
    assert extract_simple_filter(sql, SRC) is None


def test_comma_multi_table_rejected():
    sql = "SELECT * FROM raw.orders, raw.customers WHERE raw.orders.id = 1"
    assert extract_simple_filter(sql, SRC) is None


# ── rejected: complex structure ──────────────────────────────────────────────

def test_cte_rejected():
    sql = "WITH x AS (SELECT * FROM raw.orders) SELECT * FROM x WHERE status = 'a'"
    assert extract_simple_filter(sql, SRC) is None


def test_subquery_in_from_rejected():
    sql = "SELECT * FROM (SELECT * FROM raw.orders) t WHERE status = 'a'"
    assert extract_simple_filter(sql, SRC) is None


def test_subquery_in_where_rejected():
    sql = "SELECT * FROM raw.orders WHERE id IN (SELECT id FROM raw.customers)"
    assert extract_simple_filter(sql, SRC) is None


def test_union_rejected():
    sql = "SELECT * FROM raw.orders WHERE status = 'a' UNION SELECT * FROM raw.orders"
    assert extract_simple_filter(sql, SRC) is None


def test_group_by_rejected():
    sql = "SELECT status FROM raw.orders WHERE amount > 0 GROUP BY status"
    assert extract_simple_filter(sql, SRC) is None


def test_having_rejected():
    sql = "SELECT status FROM raw.orders GROUP BY status HAVING COUNT(*) > 1"
    assert extract_simple_filter(sql, SRC) is None


def test_distinct_rejected():
    sql = "SELECT DISTINCT status FROM raw.orders WHERE amount > 0"
    assert extract_simple_filter(sql, SRC) is None


def test_limit_rejected():
    sql = "SELECT * FROM raw.orders WHERE status = 'a' LIMIT 10"
    assert extract_simple_filter(sql, SRC) is None


def test_aggregate_in_select_rejected():
    sql = "SELECT COUNT(*) FROM raw.orders WHERE status = 'a'"
    assert extract_simple_filter(sql, SRC) is None


def test_function_in_where_rejected():
    sql = "SELECT * FROM raw.orders WHERE LOWER(status) = 'completed'"
    assert extract_simple_filter(sql, SRC) is None


def test_arithmetic_in_where_rejected():
    sql = "SELECT * FROM raw.orders WHERE amount + 1 > 5"
    assert extract_simple_filter(sql, SRC) is None


def test_like_in_where_rejected():
    sql = "SELECT * FROM raw.orders WHERE status LIKE 'comp%'"
    assert extract_simple_filter(sql, SRC) is None


# ── rejected: misc ───────────────────────────────────────────────────────────

def test_no_where_returns_none():
    assert extract_simple_filter("SELECT * FROM raw.orders", SRC) is None


def test_unparseable_returns_none():
    assert extract_simple_filter("SELECT FROM WHERE", SRC) is None


def test_none_or_empty_returns_none():
    assert extract_simple_filter(None, SRC) is None
    assert extract_simple_filter("   ", SRC) is None


def test_from_table_mismatch_returns_none():
    sql = "SELECT * FROM raw.other WHERE status = 'a'"
    assert extract_simple_filter(sql, SRC) is None
