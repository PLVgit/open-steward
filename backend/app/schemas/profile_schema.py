from pydantic import BaseModel

from app.models.finding import ValidationFinding
from app.models.table_profile import TableProfile


class ProfileResponse(BaseModel):
    profile: TableProfile
    findings: list[ValidationFinding]
