"""The FastAPI app. Served same-origin behind CloudFront at /api/*, so every
route here is defined with that prefix baked in — no CORS middleware exists
anywhere in this codebase because the browser never sees a cross-origin
request."""

from fastapi import FastAPI

from oya.api.auth import router as auth_router

app = FastAPI(title="Off Yo Ass API")
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
