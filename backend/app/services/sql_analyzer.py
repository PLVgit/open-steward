import sqlglot
import sqlglot.expressions as exp

from app.models.finding import ValidationFinding
from app.models.pipeline_job import PipelineJob


def analyze_sql(jobs: list[PipelineJob]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for job in jobs:
        if job.sql_query is None:
            continue
        findings.extend(_analyze_job(job))
    return findings


def _analyze_job(job: PipelineJob) -> list[ValidationFinding]:
    try:
        query = sqlglot.parse_one(job.sql_query)
    except sqlglot.errors.ParseError as exc:
        return [
            ValidationFinding(
                finding_type="unparseable_sql",
                severity="warning",
                message=f"SQL for job '{job.config_key}' could not be parsed: {exc}",
                affected_job=job.config_key,
                recommendation="Review the SQL syntax and ensure it is valid standard SQL.",
            )
        ]

    findings: list[ValidationFinding] = []

    if _has_select_star(query):
        findings.append(
            ValidationFinding(
                finding_type="select_star",
                severity="warning",
                message=f"Job '{job.config_key}' uses SELECT *, which may expose unexpected columns to downstream consumers.",
                affected_job=job.config_key,
                recommendation="Replace SELECT * with an explicit column list.",
            )
        )

    if _has_explicit_cast(query):
        findings.append(
            ValidationFinding(
                finding_type="explicit_cast",
                severity="warning",
                message=f"Job '{job.config_key}' contains a CAST or TRY_CAST expression that may silently change data types.",
                affected_job=job.config_key,
                recommendation="Verify that the cast is intentional and that downstream consumers expect the converted type.",
            )
        )

    if _has_cross_join(query):
        findings.append(
            ValidationFinding(
                finding_type="cross_join",
                severity="error",
                message=f"Job '{job.config_key}' contains a CROSS JOIN, which may produce an unintended cartesian product.",
                affected_job=job.config_key,
                recommendation="Replace the CROSS JOIN with an INNER JOIN or LEFT JOIN with an explicit ON condition.",
            )
        )

    if _is_full_load_without_filter(job, query):
        findings.append(
            ValidationFinding(
                finding_type="missing_filter_on_full_load",
                severity="info",
                message=(
                    f"Job '{job.config_key}' is a full load with no WHERE or LIMIT clause. "
                    "It will replace the entire target table on every run."
                ),
                affected_job=job.config_key,
                recommendation="Confirm this full replacement is intentional, or add a WHERE/LIMIT clause to scope the load.",
            )
        )

    return findings


def _has_select_star(query: exp.Expression) -> bool:
    for select in query.find_all(exp.Select):
        for projection in select.expressions:
            if isinstance(projection, exp.Star):
                return True
            # A qualified star (SELECT t.*) parses as a Column wrapping a Star.
            if isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
                return True
    return False


def _has_explicit_cast(query: exp.Expression) -> bool:
    return bool(query.find(exp.Cast) or query.find(exp.TryCast))


def _has_cross_join(query: exp.Expression) -> bool:
    for join in query.find_all(exp.Join):
        if join.kind and join.kind.upper() == "CROSS":
            return True
    return False


def _is_full_load_without_filter(job: PipelineJob, query: exp.Expression) -> bool:
    if job.load_type != "full":
        return False
    has_where = query.find(exp.Where) is not None
    has_limit = query.find(exp.Limit) is not None
    return not has_where and not has_limit
