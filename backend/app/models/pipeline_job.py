from pydantic import BaseModel, Field


class PipelineJob(BaseModel):
    config_key: str
    pipeline_name: str
    enabled: bool
    source_table: str
    target_table: str
    sql_query: str | None = None
    execution_order: int | None = None
    primary_key: str | None = None
    load_type: str | None = None
    # Additional upstream tables beyond source_table (e.g. the other side of a
    # join, or a multi-parent dbt model). Additive and empty for CSV configs,
    # so existing behavior is unchanged. source_table remains the primary
    # dependency used by reconciliation.
    depends_on: list[str] = Field(default_factory=list)
