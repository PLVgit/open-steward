import re

from app.adapters.data_source import DataSource
from app.models.finding import ValidationFinding
from app.models.table_profile import ColumnProfile, TableProfile

_VALID_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def profile_table(table_name: str, data_source: DataSource) -> TableProfile:
    # Source-agnostic existence check: file-backed sources raise
    # FileNotFoundError themselves, but database-backed sources raise their
    # driver's catalog error — normalize both to FileNotFoundError here.
    if not data_source.table_exists(table_name):
        raise FileNotFoundError(f"No table found for '{table_name}'.")
    schema = data_source.get_schema(table_name)
    row_count = data_source.get_row_count(table_name)

    columns: list[ColumnProfile] = []
    for col_info in schema:
        col_name = col_info.name
        if not _VALID_NAME.match(col_name):
            continue

        null_count = data_source.get_null_count(table_name, col_name)
        distinct_count = data_source.get_distinct_count(table_name, col_name)

        null_pct = round(null_count / row_count * 100, 1) if row_count > 0 else 0.0
        distinct_pct = round(distinct_count / row_count * 100, 1) if row_count > 0 else 0.0

        if col_info.dtype.upper().startswith("VARCHAR"):
            empty_string_count: int | None = data_source.get_empty_string_count(table_name, col_name)
            empty_string_pct: float | None = (
                round(empty_string_count / row_count * 100, 1) if row_count > 0 else 0.0
            )
        else:
            empty_string_count = None
            empty_string_pct = None

        columns.append(ColumnProfile(
            column_name=col_name,
            dtype=col_info.dtype,
            row_count=row_count,
            null_count=null_count,
            null_pct=null_pct,
            distinct_count=distinct_count,
            distinct_pct=distinct_pct,
            empty_string_count=empty_string_count,
            empty_string_pct=empty_string_pct,
        ))

    return TableProfile(
        table_name=table_name,
        row_count=row_count,
        column_count=len(schema),
        columns=columns,
    )


def detect_profile_findings(
    profile: TableProfile,
    *,
    null_rate_threshold_pct: float = 20.0,
    empty_string_threshold_pct: float = 10.0,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for col in profile.columns:
        findings.extend(
            _check_column(col, profile.table_name, null_rate_threshold_pct, empty_string_threshold_pct)
        )
    return findings


def _check_column(
    col: ColumnProfile,
    table_name: str,
    null_rate_threshold_pct: float,
    empty_string_threshold_pct: float,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    # all_nulls supersedes high_null_rate — both would fire for 100% null; only emit all_nulls.
    if col.row_count > 0 and col.null_count == col.row_count:
        findings.append(ValidationFinding(
            finding_type="all_nulls",
            severity="error",
            message=(
                f"Column '{col.column_name}' in '{table_name}' is entirely null: "
                f"null_count={col.null_count}, row_count={col.row_count}."
            ),
            affected_table=table_name,
            recommendation=f"Verify '{col.column_name}' is being populated correctly.",
        ))
    elif col.row_count > 0 and col.null_pct >= null_rate_threshold_pct:
        findings.append(ValidationFinding(
            finding_type="high_null_rate",
            severity="warning",
            message=(
                f"Column '{col.column_name}' in '{table_name}' has {col.null_pct}% null values "
                f"(threshold: {null_rate_threshold_pct}%)."
            ),
            affected_table=table_name,
            recommendation=f"Investigate whether null values in '{col.column_name}' are expected.",
        ))

    if col.distinct_count == 1 and col.row_count > 1:
        findings.append(ValidationFinding(
            finding_type="constant_column",
            severity="info",
            message=(
                f"Column '{col.column_name}' in '{table_name}' has only 1 distinct value "
                f"across {col.row_count} rows."
            ),
            affected_table=table_name,
            recommendation=(
                f"Confirm '{col.column_name}' is intentionally constant "
                "(e.g., a fixed category or load date)."
            ),
        ))

    if (
        col.empty_string_count is not None
        and col.empty_string_pct is not None
        and col.row_count > 0
        and col.empty_string_pct >= empty_string_threshold_pct
    ):
        findings.append(ValidationFinding(
            finding_type="high_empty_string_rate",
            severity="warning",
            message=(
                f"Column '{col.column_name}' in '{table_name}' has {col.empty_string_pct}% "
                f"empty string values (threshold: {empty_string_threshold_pct}%)."
            ),
            affected_table=table_name,
            recommendation=(
                f"Replace empty strings in '{col.column_name}' with NULL or a meaningful default."
            ),
        ))

    return findings
