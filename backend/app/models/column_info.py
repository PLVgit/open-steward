from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    dtype: str
