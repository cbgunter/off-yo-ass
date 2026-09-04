"""The FastAPI app. Served same-origin behind CloudFront at /api/*, so every
route here is defined with that prefix baked in — no CORS middleware exists
anywhere in this codebase because the browser never sees a cross-origin
request."""

from fastapi import FastAPI

from oya.api.auth import router as auth_router
from oya.api.dashboard import router as dashboard_router
from oya.api.push import router as push_router
from oya.api.quicklog import router as quicklog_router
from oya.api.sources import router as sources_router

app = FastAPI(title="Off Yo Ass API")
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(sources_router)
app.include_router(quicklog_router)
app.include_router(push_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
