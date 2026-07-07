import csv
from pathlib import Path

from app.models.pipeline_job import PipelineJob

REQUIRED_COLUMNS = {"config_key", "pipeline_name", "enabled", "source_table", "target_table"}
# Deterministic field order for per-row validation error messages.
_REQUIRED_ORDER = ("config_key", "pipeline_name", "enabled", "source_table", "target_table")
_TRUTHY = {"true", "1", "yes"}


class CsvAdapter:
    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)

    def load(self) -> list[PipelineJob]:
        if not self._path.exists():
            raise FileNotFoundError(f"Config file not found: {self._path}")

        with self._path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return []

            missing = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"CSV is missing required columns: {sorted(missing)}"
                )

            # Header is line 1, so data rows start at line 2.
            return [self._parse_row(row, line) for line, row in enumerate(reader, start=2)]

    def _parse_row(self, row: dict, line: int) -> PipelineJob:
        # DictReader yields None for cells missing from short rows. Required
        # fields must be present and non-empty, so a malformed row fails with a
        # clear message instead of an AttributeError deep inside parsing.
        for field in _REQUIRED_ORDER:
            value = row.get(field)
            if value is None or not value.strip():
                raise ValueError(f"Row {line}: missing value for required column '{field}'.")

        raw_order = (row.get("execution_order") or "").strip()
        try:
            execution_order = int(raw_order) if raw_order else None
        except ValueError:
            raise ValueError(
                f"Row {line}: invalid execution_order {raw_order!r}; expected an integer."
            ) from None

        # Optional `tags` column: comma- or semicolon-separated labels
        # (e.g. "temp;hide_from_graph"). Absent column → no tags.
        raw_tags = (row.get("tags") or "").strip()
        tags = (
            [t.strip() for t in raw_tags.replace(";", ",").split(",") if t.strip()]
            if raw_tags
            else []
        )

        return PipelineJob(
            config_key=row["config_key"],
            pipeline_name=row["pipeline_name"],
            enabled=row["enabled"].strip().lower() in _TRUTHY,
            source_table=row["source_table"],
            target_table=row["target_table"],
            sql_query=row.get("sql_query") or None,
            execution_order=execution_order,
            primary_key=row.get("primary_key") or None,
            load_type=row.get("load_type") or None,
            tags=tags,
        )
