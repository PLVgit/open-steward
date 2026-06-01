from app.adapters.data_source import DataSource
from app.models.finding import ValidationFinding
from app.models.pipeline_job import PipelineJob

# TODO — row loss tolerance:
# Future versions should support configurable thresholds per job:
# row_loss_tolerance_pct, allowed_row_loss, expected_filter_loss.
# Currently any target < source on a full-load job is flagged.

# TODO — filter-aware reconciliation:
# When a job's sql_query contains a WHERE clause, row loss may be explained by the filter.
# Future reconciliation should compute:
#   source_count           — rows before the filter
#   expected_after_filter  — rows that pass the filter (requires running filter against source data)
#   target_count           — actual rows in target
#   filtered_out_rows      = source_count - expected_after_filter
#   filtered_out_pct
#   unexpected_loss_rows   = expected_after_filter - target_count
#   unexpected_loss_pct
# If unexpected_loss_rows == 0, row loss is fully explained and row_count_drop should not fire.

# TODO — join-aware advisory statistics:
# Row loss through joins is legitimate but worth surfacing as advisory, not hard errors.
# Future statistics: join_match_rate, unmatched_left_rows, unmatched_right_rows,
# possible_many_to_many_join, possible_row_multiplication, join_key_null_rate.

# TODO — ETL-level statistics for UI:
# Future UI should display a per-ETL reconciliation panel containing:
#   source_count, target_count, lost_rows, loss_pct, target_empty,
#   primary_key_null_count, primary_key_null_pct, primary_key_duplicate_count.
# Later additions: expected_after_filter_count, filtered_out_rows, filtered_out_pct,
#   unexpected_loss_rows, unexpected_loss_pct,
#   join_match_rate, join_unmatched_rows, possible_row_multiplication.


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
        lost_rows = source_count - target_count
        # Guard against division by zero; source_count > 0 is guaranteed by the condition above.
        loss_pct = round(lost_rows / source_count * 100, 1) if source_count > 0 else 0.0
        findings.append(ValidationFinding(
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
        ))

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
