"""Tests for production single-app serving: FastAPI serving the built UI.

The SPA-shell tests are skipped when the frontend has not been built (e.g. the
backend-only CI job) — the /api alias and JSON-miss behavior is always tested.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import DIST_DIR, app

client = TestClient(app)

_HAS_UI = (DIST_DIR / "index.html").is_file()
needs_ui = pytest.mark.skipif(not _HAS_UI, reason="frontend not built (no frontend/dist)")


# ── /api alias (what the built UI calls) ──────────────────────────────────────

def test_api_alias_matches_bare_route():
    bare = client.get("/pipelines/", params={"file": "demo_config.csv"})
    alias = client.get("/api/pipelines/", params={"file": "demo_config.csv"})
    assert alias.status_code == 200
    assert alias.json() == bare.json()


def test_api_alias_covers_all_routers():
    assert client.get("/api/graph/", params={"file": "demo_config.csv"}).status_code == 200
    assert client.get("/api/findings/", params={"file": "demo_config.csv"}).status_code == 200
    assert client.get("/api/statistics/", params={"file": "demo_config.csv"}).status_code == 200
    assert client.get("/api/profile/", params={"table": "staging.orders", "data_dir": "."}).status_code == 200


def test_unknown_api_path_is_json_404_not_html():
    r = client.get("/api/nonexistent")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


# ── slashless API paths never fall into the SPA ───────────────────────────────

def test_slashless_canonical_pipelines_redirects():
    r = client.get("/pipelines", params={"file": "demo_config.csv"}, follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].endswith("/pipelines/?file=demo_config.csv")


def test_slashless_canonical_pipelines_resolves_to_json():
    r = client.get("/pipelines", params={"file": "demo_config.csv"})  # follows redirect
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_slashless_api_alias_redirects_for_every_root():
    for root in ("pipelines", "graph", "findings", "statistics", "profile"):
        r = client.get(f"/api/{root}", follow_redirects=False)
        assert r.status_code == 307, root
        assert r.headers["location"].endswith(f"/api/{root}/"), root


def test_slashless_api_alias_resolves_to_json():
    r = client.get("/api/pipelines", params={"file": "demo_config.csv"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_only_namespace_miss_is_json_404_not_html():
    r = client.get("/pipelines/nope/extra")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_api_alias_hidden_from_openapi_schema():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/pipelines/" in paths
    assert not any(p.startswith("/api/") for p in paths)


# ── docs keep working alongside the catch-all ─────────────────────────────────

def test_docs_still_served():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


# ── SPA shell + assets ────────────────────────────────────────────────────────

@needs_ui
def test_root_serves_the_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in r.text


@needs_ui
def test_client_side_routes_serve_spa_shell():
    # A hard reload on any frontend route must load the app, not 404 or JSON.
    # (These names double as API roots at their slashed form — the slashless
    # form belongs to the UI.)
    for route in ("/graph", "/findings", "/statistics", "/profile"):
        r = client.get(route)
        assert r.status_code == 200, route
        assert r.headers["content-type"].startswith("text/html"), route


@needs_ui
def test_js_asset_served_with_module_safe_mime():
    index = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    match = re.search(r'src="/(assets/[^"]+\.js)"', index)
    assert match, "built index.html should reference a JS bundle"
    r = client.get(f"/{match.group(1)}")
    assert r.status_code == 200
    # Browsers refuse ES modules served as text/plain — must be a JS type.
    assert "javascript" in r.headers["content-type"]


def test_path_traversal_never_leaves_dist():
    r = client.get("/..%2f..%2fpyproject.toml")
    # Either the SPA shell (UI built) or the JSON hint (not built) — never the file.
    assert "setuptools" not in r.text


def test_missing_ui_gives_helpful_hint_or_shell():
    r = client.get("/")
    if _HAS_UI:
        assert r.status_code == 200
    else:
        assert r.status_code == 404
        assert "npm run build" in r.json()["detail"]
