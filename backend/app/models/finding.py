from pydantic import BaseModel


class ValidationFinding(BaseModel):
    finding_type: str
    severity: str
    message: str
    affected_job: str | None = None
    affected_table: str | None = None
    recommendation: str | None = None
