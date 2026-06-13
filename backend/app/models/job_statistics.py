from pydantic import BaseModel


class JobStatistics(BaseModel):
    """Numeric facts about one ETL job's source/target tables.

    Sits alongside ValidationFinding: findings say *what is wrong*, statistics
    say *what happened numerically*. None means "not computable" (a table is
    missing, or the job has no primary key) — distinct from 0.
    """

    config_key: str
    pipeline_name: str
    source_table: str
    target_table: str

    source_count: int | None         # None when the source table is missing
    target_count: int | None         # None when the target table is missing

    lost_rows: int | None            # source_count - target_count, never negative
    loss_pct: float | None           # 0.0–100.0, rounded to 1 decimal
    target_empty: bool | None        # True when target_count == 0; None if unknown

    primary_key: str | None          # echoed from the job config
    primary_key_null_count: int | None       # None when no PK or target missing
    primary_key_null_pct: float | None        # 0.0–100.0, rounded to 1 decimal
    primary_key_duplicate_count: int | None   # distinct keys appearing > once
