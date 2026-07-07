from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app import __version__
from app.api.routes import configs, findings, graph, pipelines, profile, statistics

app = FastAPI(title="Open Steward", version=__version__)

_ROUTERS = (
    (pipelines.router, "/pipelines", "pipelines"),
    (graph.router, "/graph", "graph"),
    (findings.router, "/findings", "findings"),
    (statistics.router, "/statistics", "statistics"),
    (profile.router, "/profile", "profile"),
    (configs.router, "/configs", "configs"),
)

for router, prefix, tag in _ROUTERS:
    app.include_router(router, prefix=prefix, tags=[tag])
    # The built UI calls the API under "/api" (mirroring the Vite dev proxy),
    # so the same routers are aliased there. Hidden from the OpenAPI schema to
    # keep /docs free of duplicates — the bare paths stay canonical.
    app.include_router(router, prefix=f"/api{prefix}", include_in_schema=False)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Liveness + version, for monitoring and the UI."""
    return {"status": "ok", "version": __version__}


@app.get("/api/health", include_in_schema=False)
async def health_alias() -> dict:
    return {"status": "ok", "version": __version__}


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ── production UI serving ─────────────────────────────────────────────────────
# When the frontend has been built (`npm run build` in frontend/), FastAPI
# serves the compiled single-page app itself, so Open Steward runs as ONE app:
# `open-steward serve` → UI + API on the same port. Vite dev mode is unaffected
# (it serves the UI itself and proxies /api here).

DIST_DIR = (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist").resolve()

# Explicit media types for the asset extensions Vite emits. mimetypes can be
# misconfigured by the OS registry (e.g. .js → text/plain on some Windows
# machines), which breaks ES-module loading in browsers.
_MEDIA_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

_UI_MISSING = {
    "detail": (
        "UI build not found. Build it with 'npm run build' in frontend/, "
        "then reload — or use the API directly (interactive docs at /docs)."
    )
}


def _spa_shell() -> FileResponse | JSONResponse:
    index = DIST_DIR / "index.html"
    if not index.is_file():
        return JSONResponse(status_code=404, content=_UI_MISSING)
    return FileResponse(index, media_type="text/html")


@app.get("/", include_in_schema=False, response_model=None)
async def ui_index() -> FileResponse | JSONResponse:
    return _spa_shell()


# All canonical API roots (each served at "/<root>/" and "/api/<root>/").
_API_ROOTS = {"pipelines", "graph", "findings", "statistics", "profile", "configs"}
# Roots that exist ONLY as API namespaces — no SPA route lives there. The other
# roots double as SPA client routes (/graph, /findings, …), which own the
# slashless form in the browser; their API canonical stays the slashed form.
_API_ONLY_ROOTS = {"pipelines", "configs"}

_JSON_404 = {"detail": "Not Found"}


@app.get("/{path:path}", include_in_schema=False, response_model=None)
async def ui_static_or_spa(path: str, request: Request) -> Response:
    """Serve built UI assets; unknown paths fall back to the SPA shell so
    client-side routes (/graph, /findings, …) survive a full page load.

    API namespaces never serve HTML: a slashless API root redirects to its
    canonical slashed form (query preserved), and any other miss under an API
    namespace answers in JSON."""
    segments = [s for s in path.split("/") if s]

    # /api/* — the alias namespace the built UI calls.
    if segments and segments[0] == "api":
        if len(segments) == 2 and segments[1] in _API_ROOTS:
            return RedirectResponse(
                request.url.replace(path=f"/api/{segments[1]}/"), status_code=307
            )
        return JSONResponse(status_code=404, content=_JSON_404)

    # API-only canonical namespaces (e.g. /pipelines…).
    if segments and segments[0] in _API_ONLY_ROOTS:
        if len(segments) == 1:
            return RedirectResponse(
                request.url.replace(path=f"/{segments[0]}/"), status_code=307
            )
        return JSONResponse(status_code=404, content=_JSON_404)

    candidate = (DIST_DIR / path).resolve()
    # Confinement: never serve anything outside the built dist directory.
    if candidate.is_file() and candidate.is_relative_to(DIST_DIR):
        return FileResponse(candidate, media_type=_MEDIA_TYPES.get(candidate.suffix.lower()))
    return _spa_shell()
