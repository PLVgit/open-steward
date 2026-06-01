from pydantic import BaseModel


class ColumnProfile(BaseModel):
    column_name: str
    dtype: str
    row_count: int
    null_count: int
    null_pct: float          # 0.0–100.0, rounded to 1 decimal
    distinct_count: int
    distinct_pct: float      # 0.0–100.0, rounded to 1 decimal
    empty_string_count: int | None   # None for non-VARCHAR columns
    empty_string_pct: float | None   # None for non-VARCHAR columns; rounded to 1 decimal


class TableProfile(BaseModel):
    table_name: str
    row_count: int
    column_count: int        # total columns in schema (including any skipped)
    columns: list[ColumnProfile]
