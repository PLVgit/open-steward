"""Join-aware advisory statistics — the join stage of transformation-aware
reconciliation.

For a job whose SQL is a simple two-table INNER/LEFT join (optionally after a
simple left WHERE), explain the row count as a staged chain:

    source_count -> after_filter_count -> expected_after_join_count -> target_count

and surface advisory findings about unmatched rows, null keys and possible row
multiplication. All counts are scalar aggregates; the join result is never
materialized. Findings are advisory (info/warning), never errors.
"""

from app.adapters.data_source import DataSource
from app.models.finding import ValidationFinding
from app.models.pipeline_job import PipelineJob
from app.services.join_analyzer import JoinInfo, extract_simple_join


def analyze_job_join(
    job: PipelineJob,
    ds: DataSource,
    source_count: int,
    target_count: int,
    *,
    row_loss_tolerance_pct: float = 0.0,
) -> list[ValidationFinding] | None:
    """Return staged + advisory join findings, or None when the job is not an
    analyzable simple join (so the caller can fall back to other behavior).

    A loss at or below `row_loss_tolerance_pct` (relative to the expected
    post-join count) suppresses the unexpected_row_loss_after_join warning;
    advisory findings are unaffected."""
    info = extract_simple_join(job.sql_query)
    if info is None:
        return None
    # The join's left table must be the job's declared source, and both
    # snapshots must be present.
    if info.left_table.lower() != job.source_table.lower():
        return None
    if not ds.table_exists(info.left_table) or not ds.table_exists(info.right_table):
        return None

    try:
        metrics = _compute_metrics(info, ds, source_count)
    except Exception:
        # Any metric error (e.g. a join key column missing) -> fall back safely.
        return None

    findings: list[ValidationFinding] = []
    staged = _staged_finding(job, info, metrics, target_count, row_loss_tolerance_pct)
    if staged is not None:
        findings.append(staged)
    findings.extend(_advisory_findings(job, info, metrics))
    return findings


class _Metrics:
    def __init__(self) -> None:
        self.source_count = 0
        self.after_filter_count = 0
        self.right_row_count = 0
        self.left_key_null_count = 0
        self.right_key_null_count = 0
        self.left_duplicate_key_count = 0
        self.right_duplicate_key_count = 0
        self.unmatched_left_rows = 0
        self.expected_after_join_count = 0


def _compute_metrics(info: JoinInfo, ds: DataSource, source_count: int) -> _Metrics:
    m = _Metrics()
    m.source_count = source_count
    m.after_filter_count = (
        ds.get_filtered_row_count(info.left_table, info.where_clause)
        if info.where_clause
        else source_count
    )
    m.right_row_count = ds.get_row_count(info.right_table)
    m.left_key_null_count = ds.get_null_count(info.left_table, info.left_key)
    m.right_key_null_count = ds.get_null_count(info.right_table, info.right_key)
    m.left_duplicate_key_count = ds.get_duplicate_key_count(info.left_table, info.left_key)
    m.right_duplicate_key_count = ds.get_duplicate_key_count(info.right_table, info.right_key)
    m.unmatched_left_rows = ds.get_unmatched_left_count(
        info.left_table, info.left_key, info.right_table, info.right_key, info.where_clause
    )
    m.expected_after_join_count = ds.get_join_output_row_count(
        info.left_table,
        info.left_key,
        info.right_table,
        info.right_key,
        info.join_type,
        info.where_clause,
    )
    return m


def _staged_finding(
    job: PipelineJob,
    info: JoinInfo,
    m: _Metrics,
    target_count: int,
    tolerance_pct: float = 0.0,
) -> ValidationFinding | None:
    filtered_out_rows = m.source_count - m.after_filter_count
    join_row_delta = m.expected_after_join_count - m.after_filter_count

    parts = [
        f"source_count={m.source_count}",
        f"after_filter_count={m.after_filter_count}",
        f"expected_after_join_count={m.expected_after_join_count}",
        f"target_count={target_count}",
    ]
    if info.where_clause:
        parts.insert(2, f"filtered_out_rows={filtered_out_rows}")
    parts.append(f"join_row_delta={join_row_delta}")

    if target_count == m.expected_after_join_count:
        return ValidationFinding(
            finding_type="row_count_change_explained_by_transformations",
            severity="info",
            message=(
                "Row-count change is explained by the job's transformations "
                f"({info.join_type} join" + (" after a WHERE filter" if info.where_clause else "")
                + "): " + ", ".join(parts) + "."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                "No action needed — the target row count matches the expected count "
                "after applying the job's filter and join."
            ),
        )

    if target_count < m.expected_after_join_count:
        unexpected_loss_rows = m.expected_after_join_count - target_count
        if (
            tolerance_pct > 0
            and m.expected_after_join_count > 0
            and (unexpected_loss_rows / m.expected_after_join_count) * 100 <= tolerance_pct
        ):
            return None  # loss within tolerance — suppress the warning
        parts.append(f"unexpected_loss_rows={unexpected_loss_rows}")
        return ValidationFinding(
            finding_type="unexpected_row_loss_after_join",
            severity="warning",
            message=(
                "Target has fewer rows than the job's filter and join explain: "
                + ", ".join(parts) + "."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                "Investigate row loss beyond the modelled transformations — e.g. extra "
                "filtering, failed inserts, or a step dropping rows."
            ),
        )

    unexpected_surplus_rows = target_count - m.expected_after_join_count
    parts.append(f"unexpected_surplus_rows={unexpected_surplus_rows}")
    return ValidationFinding(
        finding_type="unexpected_row_surplus_after_join",
        severity="warning",
        message=(
            "Target has more rows than the job's filter and join explain: "
            + ", ".join(parts) + "."
        ),
        affected_job=job.config_key,
        affected_table=job.target_table,
        recommendation=(
            "Investigate the extra rows — e.g. duplicate inserts, an unmodelled join "
            "fan-out, or appended data."
        ),
    )


def _advisory_findings(job: PipelineJob, info: JoinInfo, m: _Metrics) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    if m.unmatched_left_rows > 0:
        match_rate = (
            round((m.after_filter_count - m.unmatched_left_rows) / m.after_filter_count * 100, 1)
            if m.after_filter_count > 0
            else 0.0
        )
        if info.join_type == "INNER":
            findings.append(ValidationFinding(
                finding_type="join_unmatched_rows",
                severity="warning",
                message=(
                    f"INNER join drops {m.unmatched_left_rows} unmatched left rows: "
                    f"after_filter_count={m.after_filter_count}, "
                    f"unmatched_left_rows={m.unmatched_left_rows}, join_match_rate={match_rate}%."
                ),
                affected_job=job.config_key,
                affected_table=job.target_table,
                recommendation=(
                    f"Confirm dropping unmatched '{info.left_table}' rows is intended; "
                    "a LEFT join would keep them."
                ),
            ))
        else:
            findings.append(ValidationFinding(
                finding_type="join_unmatched_rows",
                severity="info",
                message=(
                    f"LEFT join has {m.unmatched_left_rows} unmatched left rows (kept with NULLs): "
                    f"after_filter_count={m.after_filter_count}, "
                    f"unmatched_left_rows={m.unmatched_left_rows}, join_match_rate={match_rate}%."
                ),
                affected_job=job.config_key,
                affected_table=job.target_table,
                recommendation=(
                    f"Check whether unmatched '{info.right_table}' lookups (NULL columns) are expected."
                ),
            ))

    if m.left_key_null_count > 0 or m.right_key_null_count > 0:
        findings.append(ValidationFinding(
            finding_type="join_key_nulls",
            severity="info",
            message=(
                f"Join keys contain nulls (nulls never match): "
                f"left_key_null_count={m.left_key_null_count}, "
                f"right_key_null_count={m.right_key_null_count}."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                f"Null values in '{info.left_key}'/'{info.right_key}' silently fail to join; "
                "confirm this is expected."
            ),
        ))

    both_dup = m.left_duplicate_key_count > 0 and m.right_duplicate_key_count > 0
    if both_dup:
        findings.append(ValidationFinding(
            finding_type="possible_many_to_many_join",
            severity="warning",
            message=(
                "Both join keys have duplicate values — a many-to-many join can multiply rows: "
                f"left_duplicate_key_count={m.left_duplicate_key_count}, "
                f"right_duplicate_key_count={m.right_duplicate_key_count}."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                "Verify the join keys; a many-to-many relationship usually needs deduplication "
                "or an aggregation before joining."
            ),
        ))
    elif m.right_duplicate_key_count > 0:
        findings.append(ValidationFinding(
            finding_type="possible_row_multiplication",
            severity="warning",
            message=(
                f"Right-side join key '{info.right_key}' is not unique — matched left rows may "
                f"multiply: right_duplicate_key_count={m.right_duplicate_key_count}, "
                f"right_row_count={m.right_row_count}."
            ),
            affected_job=job.config_key,
            affected_table=job.target_table,
            recommendation=(
                f"Confirm '{info.right_table}' should have duplicate '{info.right_key}' values, "
                "or deduplicate before joining."
            ),
        ))

    return findings
