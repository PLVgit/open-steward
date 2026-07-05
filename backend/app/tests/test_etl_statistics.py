from app.models.pipeline_job import PipelineJob
from app.services.etl_statistics import compute_job_statistics


# ── fake DataSource ─────────────────────────────────────────────────────────────

class FakeDataSource:
    """In-memory DataSource stub. Tables are keyed by name; missing keys behave
    as non-existent tables."""

    def __init__(self, tables: dict[str, dict]) -> None:
        # each table dict: {"rows": int, "nulls": {col: int}, "dups": {col: int}}
        self._tables = tables

    def table_exists(self, table_name: str) -> bool:
        return table_name in self._tables

    def get_schema(self, table_name: str):
        raise NotImplementedError

    def get_row_count(self, table_name: str) -> int:
        return self._tables[table_name]["rows"]

    def get_distinct_count(self, table_name: str, column: str) -> int:
        raise NotImplementedError

    def get_null_count(self, table_name: str, column: str) -> int:
        return self._tables[table_name].get("nulls", {}).get(column, 0)

    def get_empty_string_count(self, table_name: str, column: str) -> int:
        raise NotImplementedError

    def get_duplicate_key_count(self, table_name: str, primary_key: str) -> int:
        return self._tables[table_name].get("dups", {}).get(primary_key, 0)


def _job(
    source: str = "raw.orders",
    target: str = "staging.orders",
    enabled: bool = True,
    pk: str | None = "id",
    key: str = "etl_001",
) -> PipelineJob:
    return PipelineJob(
        config_key=key,
        pipeline_name="Test Job",
        enabled=enabled,
        source_table=source,
        target_table=target,
        primary_key=pk,
        load_type="full",
    )


# ── basic counts ────────────────────────────────────────────────────────────────

def test_basic_counts_populated():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 8, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    stats = compute_job_statistics([_job()], ds)
    assert len(stats) == 1
    s = stats[0]
    assert s.source_count == 10
    assert s.target_count == 8
    assert s.config_key == "etl_001"
    assert s.target_table == "staging.orders"


# ── lost_rows / loss_pct ────────────────────────────────────────────────────────

def test_lost_rows_when_target_below_source():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 8, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.lost_rows == 2
    assert s.loss_pct == 20.0


def test_no_loss_when_target_equals_source():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 10, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.lost_rows == 0
    assert s.loss_pct == 0.0


def test_lost_rows_never_negative_when_target_exceeds_source():
    ds = FakeDataSource({
        "raw.orders": {"rows": 5},
        "staging.orders": {"rows": 12, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.lost_rows == 0
    assert s.loss_pct == 0.0


def test_loss_pct_divide_by_zero_guard():
    ds = FakeDataSource({
        "raw.orders": {"rows": 0},
        "staging.orders": {"rows": 0, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.lost_rows == 0
    assert s.loss_pct == 0.0


# ── target_empty ────────────────────────────────────────────────────────────────

def test_target_empty_true_when_zero_rows():
    ds = FakeDataSource({
        "raw.orders": {"rows": 5},
        "staging.orders": {"rows": 0, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.target_empty is True


def test_target_empty_false_when_rows_present():
    ds = FakeDataSource({
        "raw.orders": {"rows": 5},
        "staging.orders": {"rows": 5, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.target_empty is False


# ── primary key metrics ─────────────────────────────────────────────────────────

def test_primary_key_metrics_populated():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 10, "nulls": {"id": 2}, "dups": {"id": 1}},
    })
    s = compute_job_statistics([_job(pk="id")], ds)[0]
    assert s.primary_key == "id"
    assert s.primary_key_null_count == 2
    assert s.primary_key_null_pct == 20.0
    assert s.primary_key_duplicate_count == 1


def test_primary_key_none_yields_none_metrics():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 10},
    })
    s = compute_job_statistics([_job(pk=None)], ds)[0]
    assert s.primary_key is None
    assert s.primary_key_null_count is None
    assert s.primary_key_null_pct is None
    assert s.primary_key_duplicate_count is None


def test_primary_key_null_pct_divide_by_zero_guard():
    ds = FakeDataSource({
        "raw.orders": {"rows": 5},
        "staging.orders": {"rows": 0, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    s = compute_job_statistics([_job(pk="id")], ds)[0]
    assert s.primary_key_null_pct == 0.0


def test_misconfigured_primary_key_yields_none_metrics():
    # The PK column doesn't exist in the target snapshot. That is "not
    # computable" (None), not an error that fails the whole response.
    class RaisingPkDataSource(FakeDataSource):
        def get_null_count(self, table_name: str, column: str) -> int:
            raise ValueError(f"Column '{column}' does not exist in the table.")

    ds = RaisingPkDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 8},
    })
    s = compute_job_statistics([_job(pk="missing_col")], ds)[0]
    assert s.primary_key == "missing_col"
    assert s.primary_key_null_count is None
    assert s.primary_key_null_pct is None
    assert s.primary_key_duplicate_count is None
    # Non-PK metrics are unaffected.
    assert s.source_count == 10
    assert s.target_count == 8


# ── missing tables ──────────────────────────────────────────────────────────────

def test_missing_source_yields_none_and_keeps_job():
    ds = FakeDataSource({
        "staging.orders": {"rows": 8, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    stats = compute_job_statistics([_job()], ds)
    assert len(stats) == 1
    s = stats[0]
    assert s.source_count is None
    assert s.target_count == 8
    assert s.lost_rows is None
    assert s.loss_pct is None
    # PK metrics still computable because the target exists
    assert s.primary_key_null_count == 0


def test_missing_target_yields_none_metrics():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
    })
    s = compute_job_statistics([_job()], ds)[0]
    assert s.target_count is None
    assert s.target_empty is None
    assert s.lost_rows is None
    assert s.loss_pct is None
    assert s.primary_key_null_count is None
    assert s.primary_key_duplicate_count is None


# ── enabled filtering ───────────────────────────────────────────────────────────

def test_disabled_job_excluded():
    ds = FakeDataSource({
        "raw.orders": {"rows": 10},
        "staging.orders": {"rows": 8, "nulls": {"id": 0}, "dups": {"id": 0}},
    })
    stats = compute_job_statistics(
        [_job(enabled=False, key="etl_disabled"), _job(key="etl_enabled")],
        ds,
    )
    assert [s.config_key for s in stats] == ["etl_enabled"]
