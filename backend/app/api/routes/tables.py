from pydantic import BaseModel

from fastapi import APIRouter, Depends

from app.adapters.data_source import DataSource
from app.api.deps import get_data_source

router = APIRouter()


class TableListing(BaseModel):
    tables: list[str]


@router.get("/", response_model=TableListing)
def list_tables(data_source: DataSource = Depends(get_data_source)) -> TableListing:
    """List the tables available in the selected data directory or database —
    feeds the Profile page's table suggestions."""
    return TableListing(tables=data_source.list_tables())
