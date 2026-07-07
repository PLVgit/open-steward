from pydantic import BaseModel

from fastapi import APIRouter

from app.api.deps import get_config_dir

router = APIRouter()


class ConfigListing(BaseModel):
    """What's selectable in the current config directory."""

    files: list[str]      # config CSVs (usable as ?file=)
    manifests: list[str]  # dbt manifest JSONs (usable as ?manifest=)


@router.get("/", response_model=ConfigListing)
def list_configs() -> ConfigListing:
    """List the config CSVs and dbt manifests available to the API — feeds the
    UI's config selector and makes OPEN_STEWARD_CONFIG_DIR discoverable."""
    root = get_config_dir()
    if not root.is_dir():
        return ConfigListing(files=[], manifests=[])
    return ConfigListing(
        files=sorted(p.name for p in root.glob("*.csv") if p.is_file()),
        manifests=sorted(p.name for p in root.glob("*.json") if p.is_file()),
    )
