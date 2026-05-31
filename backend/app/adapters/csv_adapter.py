import csv
from pathlib import Path

from app.models.pipeline_job import PipelineJob

REQUIRED_COLUMNS = {"config_key", "pipeline_name", "enabled", "source_table", "target_table"}
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

            return [self._parse_row(row) for row in reader]

    def _parse_row(self, row: dict) -> PipelineJob:
        raw_order = row.get("execution_order", "").strip()
        return PipelineJob(
            config_key=row["config_key"],
            pipeline_name=row["pipeline_name"],
            enabled=row["enabled"].strip().lower() in _TRUTHY,
            source_table=row["source_table"],
            target_table=row["target_table"],
            sql_query=row.get("sql_query") or None,
            execution_order=int(raw_order) if raw_order else None,
            primary_key=row.get("primary_key") or None,
            load_type=row.get("load_type") or None,
        )
