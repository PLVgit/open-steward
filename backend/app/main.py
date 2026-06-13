from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import findings, graph, pipelines, statistics

app = FastAPI(title="Open Steward", version="0.1.0")

app.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(findings.router, prefix="/findings", tags=["findings"])
app.include_router(statistics.router, prefix="/statistics", tags=["statistics"])


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})
