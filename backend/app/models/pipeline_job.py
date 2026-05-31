from pydantic import BaseModel


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
