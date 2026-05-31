from pydantic import BaseModel


class EdgeDetail(BaseModel):
    source: str
    target: str
    config_key: str


class GraphResponse(BaseModel):
    nodes: list[str]
    edges: list[EdgeDetail]
    execution_order: list[str] | None
    cycle_detected: bool
