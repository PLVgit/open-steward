from app.services.join_analyzer import extract_simple_join


# ── supported joins ──────────────────────────────────────────────────────────

def test_inner_join_extracted():
    sql = "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id"
    info = extract_simple_join(sql)
    assert info is not None
    assert info.join_type == "INNER"
    assert info.left_table == "raw.orders"
    assert info.right_table == "raw.customers"
    assert info.left_key == "cid"
    assert info.right_key == "id"
    assert info.where_clause is None


def test_explicit_inner_join_extracted():
    sql = "SELECT * FROM raw.orders o INNER JOIN raw.customers c ON o.cid = c.id"
    assert extract_simple_join(sql).join_type == "INNER"


def test_left_join_extracted():
    sql = "SELECT * FROM raw.orders o LEFT JOIN raw.customers c ON o.cid = c.id"
    info = extract_simple_join(sql)
    assert info is not None
    assert info.join_type == "LEFT"


def test_key_order_independent_of_on_side():
    # right.key = left.key should still map correctly
    sql = "SELECT * FROM raw.orders o JOIN raw.customers c ON c.id = o.cid"
    info = extract_simple_join(sql)
    assert info.left_key == "cid"
    assert info.right_key == "id"


def test_left_where_extracted_and_qualifier_stripped():
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "WHERE o.status = 'completed'"
    )
    info = extract_simple_join(sql)
    assert info is not None
    assert info.where_clause == "status = 'completed'"


# ── rejected join shapes ─────────────────────────────────────────────────────

def test_right_join_rejected():
    sql = "SELECT * FROM raw.orders o RIGHT JOIN raw.customers c ON o.cid = c.id"
    assert extract_simple_join(sql) is None


def test_full_join_rejected():
    sql = "SELECT * FROM raw.orders o FULL JOIN raw.customers c ON o.cid = c.id"
    assert extract_simple_join(sql) is None


def test_cross_join_rejected():
    sql = "SELECT * FROM raw.orders o CROSS JOIN raw.customers c"
    assert extract_simple_join(sql) is None


def test_two_joins_rejected():
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "JOIN raw.regions r ON c.rid = r.id"
    )
    assert extract_simple_join(sql) is None


def test_no_join_returns_none():
    assert extract_simple_join("SELECT * FROM raw.orders WHERE status = 'a'") is None


def test_composite_on_rejected():
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c "
        "ON o.cid = c.id AND o.region = c.region"
    )
    assert extract_simple_join(sql) is None


def test_non_equality_on_rejected():
    sql = "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid > c.id"
    assert extract_simple_join(sql) is None


def test_unqualified_on_column_rejected():
    sql = "SELECT * FROM raw.orders o JOIN raw.customers c ON cid = id"
    assert extract_simple_join(sql) is None


# ── rejected: complex structure ──────────────────────────────────────────────

def test_aggregate_rejected():
    sql = "SELECT COUNT(*) FROM raw.orders o JOIN raw.customers c ON o.cid = c.id"
    assert extract_simple_join(sql) is None


def test_group_by_rejected():
    sql = (
        "SELECT c.id FROM raw.orders o JOIN raw.customers c ON o.cid = c.id GROUP BY c.id"
    )
    assert extract_simple_join(sql) is None


def test_subquery_side_rejected():
    sql = (
        "SELECT * FROM (SELECT * FROM raw.orders) o JOIN raw.customers c ON o.cid = c.id"
    )
    assert extract_simple_join(sql) is None


# ── rejected: unsafe WHERE ───────────────────────────────────────────────────

def test_where_referencing_right_table_rejected():
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "WHERE c.region = 'EU'"
    )
    assert extract_simple_join(sql) is None


def test_complex_where_function_rejected():
    sql = (
        "SELECT * FROM raw.orders o JOIN raw.customers c ON o.cid = c.id "
        "WHERE LOWER(o.status) = 'completed'"
    )
    assert extract_simple_join(sql) is None


def test_unparseable_returns_none():
    assert extract_simple_join("SELECT JOIN ON") is None
    assert extract_simple_join(None) is None
