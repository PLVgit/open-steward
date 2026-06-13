from app.adapters.data_source import DataSource
from app.models.finding import ValidationFinding
from app.models.pipeline_job import PipelineJob
from app.services.filter_analyzer import extract_simple_filter

# TODO — row loss tolerance:
# Future versions should support configurable thresholds per job:
# row_loss_tolerance_pct, allowed_row_loss, expected_filter_loss.
# Currently any unexplained target < source on a full-load job is flagged.

# Filter-aware reconciliation (implemented):
# For full-load jobs whose SQL is a simple single-source WHERE filter
# (see filter_analyzer.extract_simple_filter), we compute expected_after_filter
# and compare it to target_count:
#   - target == expected  -> info  row_loss_explained_by_filter
#   - target <  expected  -> warn  unexpected_row_loss
#   - target >  expected  -> no finding (row surplus is out of scope; see below)
# Anything not provably simple (joins, subqueries, aggregates, etc.) falls back
# to row_count_drop.

# TODO — Ticket 22, join-aware advisory statistics:
# Joins legitimately change row counts (unmatched rows, fan-out, duplicate keys),
# so they are surfaced as advisory statistics, not hard errors. Future work:
#   - join_match_rate
#   - unmatched_left_rows
#   - unmatched_right_rows (where meaningful)
#   - possible_many_to_many_join
#   - possible_row_multiplication
#   - right-side duplicate join keys
#   - row count changes caused by JOINs after filters
# This is also where row surplus (target > expected_after_filter, i.e.
# unexpected_row_surplus_after_filter / row multiplication) should be handled.

# TODO — ETL-level statistics for UI:
# The per-job JobStatistics layer reports raw source/target/lost_rows numbers.
# It could later also expose filter-aware fields (expected_after_filter_count,
# filtered_out_rows/pct, unexpected_loss_rows/pct) and the join-aware advisory
# statistics above for richer UI panels.


def reconcile_jobs(
    jobs: list[PipelineJob],
    data_source: DataSource,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for job in jobs:
        findings.extend(_reconcile_job(job, data_source))
    return findings


def _reconcile_job(job: PipelineJob, ds: DataSource) -> list[ValidationFinding]:
    if not job.enabled:
        return []
    if not ds.table_exists(job.source_table) or not ds.table_exists(job.target_table):
        return []

    source_count = ds.get_row_count(job.source_table)
    target_count = ds.get_row_count(job.target_table)
    findings: list[ValidationFinding] = []

    if target_count == 0 and source_count > 0:
        findings.append(ValidationFinding(
            finding_type="empty_target",
            severity="warning",
            message=(
                f"Target table is empty while source has rows: "
                f"source_count={source_count}, target_count={target_count}."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation="Verify the ETL job ran successfully and loaded data into the target table.",
        ))

    if job.load_type == "full" and 0 < target_count < source_count:
        findings.extend(_row_drop_findings(job, ds, source_count, target_count))

    if job.primary_key:
        null_count = ds.get_null_count(job.target_table, job.primary_key)
        if null_count > 0:
            # Guard against division by zero for empty targets (null_count > 0 implies rows exist,
            # but the explicit guard keeps the intent clear).
            null_pct = round(null_count / target_count * 100, 1) if target_count > 0 else 0.0
            findings.append(ValidationFinding(
                finding_type="null_primary_key",
                severity="error",
                message=(
                    f"Primary key '{job.primary_key}' has null values in target table "
                    f"'{job.target_table}': null_count={null_count}, "
                    f"target_count={target_count}, null_pct={null_pct}%."
                ),
                affected_job=job.config_key,
                affected_table=job.target_table,
                recommendation=(
                    f"Ensure '{job.primary_key}' is always populated before loading. "
                    "Null primary keys cause issues in downstream joins and deduplication."
                ),
            ))

        dup_count = ds.get_duplicate_key_count(job.target_table, job.primary_key)
        if dup_count > 0:
            findings.append(ValidationFinding(
                finding_type="duplicate_primary_key",
                severity="error",
                message=(
                    f"Primary key '{job.primary_key}' is not unique in target table "
                    f"'{job.target_table}': duplicate_key_count={dup_count}, "
                    f"target_count={target_count}."
                ),
                affected_job=job.config_key,
                affected_table=job.target_table,
                recommendation=(
                    f"Investigate the ETL logic that writes to '{job.target_table}'. "
                    f"Deduplicate on '{job.primary_key}' before loading, or add a DISTINCT clause."
                ),
            ))

    return findings


def _row_drop_findings(
    job: PipelineJob,
    ds: DataSource,
    source_count: int,
    target_count: int,
) -> list[ValidationFinding]:
    """Explain a full-load row drop. If the job has a simple single-source WHERE
    filter, compare target_count to the filtered source count; otherwise fall
    back to a plain row_count_drop warning."""
    where_clause = extract_simple_filter(job.sql_query, job.source_table)
    expected: int | None = None
    if where_clause is not None:
        try:
            expected = ds.get_filtered_row_count(job.source_table, where_clause)
        except Exception:
            # Predicate could not be evaluated against the source — treat as
            # unsupported and fall back to the existing behavior.
            expected = None

    if expected is None:
        return [_row_count_drop(job, source_count, target_count)]
    return _filter_aware_findings(job, source_count, target_count, expected)


def _row_count_drop(job: PipelineJob, source_count: int, target_count: int) -> ValidationFinding:
    lost_rows = source_count - target_count
    # Guard against division by zero; source_count > 0 is guaranteed by the caller.
    loss_pct = round(lost_rows / source_count * 100, 1) if source_count > 0 else 0.0
    return ValidationFinding(
        finding_type="row_count_drop",
        severity="warning",
        message=(
            f"Full-load target has fewer rows than source: "
            f"source_count={source_count}, target_count={target_count}, "
            f"lost_rows={lost_rows}, loss_pct={loss_pct}%."
        ),
        affected_job=job.config_key,
        affected_table=job.target_table,
        recommendation=(
            "Check the ETL transformation for unintended filtering or data loss. "
            "Consider adding row count assertions to the pipeline."
        ),
    )


def _filter_aware_findings(
    job: PipelineJob,
    source_count: int,
    target_count: int,
    expected: int,
) -> list[ValidationFinding]:
    filtered_out_rows = source_count - expected
    filtered_out_pct = round(filtered_out_rows / source_count * 100, 1) if source_count > 0 else 0.0

    if target_count == expected:
        return [ValidationFinding(
            finding_type="row_loss_explained_by_filter",
            severity="info",
            message=(
                f"Row drop is explained by the job's WHERE filter: "
                f"source_count={source_count}, expected_after_filter_count={expected}, "
                f"target_count={target_count}, filtered_out_rows={filtered_out_rows}, "
                f"filtered_out_pct={filtered_out_pct}%."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                "No action needed — the row reduction matches the WHERE filter in the job's SQL."
            ),
        )]

    if target_count < expected:
        unexpected_loss_rows = expected - target_count
        unexpected_loss_pct = (
            round(unexpected_loss_rows / expected * 100, 1) if expected > 0 else 0.0
        )
        return [ValidationFinding(
            finding_type="unexpected_row_loss",
            severity="warning",
            message=(
                f"Target has fewer rows than the WHERE filter explains: "
                f"source_count={source_count}, expected_after_filter_count={expected}, "
                f"target_count={target_count}, filtered_out_rows={filtered_out_rows}, "
                f"filtered_out_pct={filtered_out_pct}%, "
                f"unexpected_loss_rows={unexpected_loss_rows}, "
                f"unexpected_loss_pct={unexpected_loss_pct}%."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                "Investigate row loss beyond the WHERE filter — e.g. additional implicit "
                "filtering, failed inserts, or a transformation dropping rows."
            ),
        )]

    # target_count > expected (row surplus): conservatively no finding here.
    # Row surplus / multiplication belongs to the future join-aware advisory
    # statistics ticket (see TODO at the top of this module).
    return []
