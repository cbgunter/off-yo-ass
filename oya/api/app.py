"""The FastAPI app. Served same-origin behind CloudFront at /api/*, so every
route here is defined with that prefix baked in — no CORS middleware exists
anywhere in this codebase because the browser never sees a cross-origin
request."""

from fastapi import FastAPI

from oya.api.auth import router as auth_router
from oya.api.call import router as call_router
from oya.api.dashboard import router as dashboard_router
from oya.api.notes import router as notes_router
from oya.api.push import router as push_router
from oya.api.question import router as question_router
from oya.api.quicklog import router as quicklog_router
from oya.api.sources import router as sources_router

app = FastAPI(title="Off Yo Ass API")
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(sources_router)
app.include_router(quicklog_router)
app.include_router(push_router)
app.include_router(call_router)
app.include_router(notes_router)
app.include_router(question_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
