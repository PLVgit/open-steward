from app.adapters.data_source import DataSource
from app.models.job_statistics import JobStatistics
from app.models.pipeline_job import PipelineJob

# This module is the numeric counterpart to reconciliation_engine. It computes
# the per-job metrics a future UI panel will display, while findings continue to
# carry the judgements. The two layers independently compute their counts today.
#
# TODO — single source of truth:
# A future ticket could refactor reconcile_jobs to derive its findings from
# JobStatistics instead of recomputing counts, removing the duplication. Kept
# separate for now so existing reconciliation behavior is untouched.
#
# TODO — disabled jobs:
# Statistics currently mirror reconcile and cover enabled jobs only. If the UI
# later needs disabled jobs too, include them here and mark them accordingly.
#
# TODO — extra_rows / extra_pct:
# When target_count > source_count (legitimate for incremental loads), a future
# enhancement could report extra_rows / extra_pct. Out of scope for this ticket.


def compute_job_statistics(
    jobs: list[PipelineJob],
    data_source: DataSource,
) -> list[JobStatistics]:
    """Compute numeric statistics for each enabled job's source/target tables."""
    stats: list[JobStatistics] = []
    for job in jobs:
        if not job.enabled:
            continue
        stats.append(_compute_job(job, data_source))
    return stats


def _compute_job(job: PipelineJob, ds: DataSource) -> JobStatistics:
    source_count = ds.get_row_count(job.source_table) if ds.table_exists(job.source_table) else None
    target_count = ds.get_row_count(job.target_table) if ds.table_exists(job.target_table) else None

    lost_rows: int | None = None
    loss_pct: float | None = None
    if source_count is not None and target_count is not None:
        # lost_rows is never negative: target >= source means no rows were lost.
        if target_count < source_count:
            lost_rows = source_count - target_count
            loss_pct = round(lost_rows / source_count * 100, 1) if source_count > 0 else 0.0
        else:
            lost_rows = 0
            loss_pct = 0.0

    target_empty = (target_count == 0) if target_count is not None else None

    pk_null_count: int | None = None
    pk_null_pct: float | None = None
    pk_duplicate_count: int | None = None
    if job.primary_key and target_count is not None:
        try:
            pk_null_count = ds.get_null_count(job.target_table, job.primary_key)
            pk_null_pct = round(pk_null_count / target_count * 100, 1) if target_count > 0 else 0.0
            pk_duplicate_count = ds.get_duplicate_key_count(job.target_table, job.primary_key)
        except Exception:
            # A misconfigured primary key (e.g. the column is missing from the
            # target snapshot) is "not computable", not an error — report None
            # rather than failing the whole statistics response.
            pk_null_count = None
            pk_null_pct = None
            pk_duplicate_count = None

    return JobStatistics(
        config_key=job.config_key,
        pipeline_name=job.pipeline_name,
        source_table=job.source_table,
        target_table=job.target_table,
        source_count=source_count,
        target_count=target_count,
        lost_rows=lost_rows,
        loss_pct=loss_pct,
        target_empty=target_empty,
        primary_key=job.primary_key,
        primary_key_null_count=pk_null_count,
        primary_key_null_pct=pk_null_pct,
        primary_key_duplicate_count=pk_duplicate_count,
    )
