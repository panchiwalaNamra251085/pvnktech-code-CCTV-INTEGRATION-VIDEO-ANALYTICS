from fastapi import FastAPI

from app.api.sites import router as sites_router
from app.api.v1.router import router as v1_router
from app.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)


# ============================================================
# Sites API
# ============================================================

app.include_router(
    sites_router,
    prefix="/api/v1",
)


# ============================================================
# Cameras API
# ============================================================

app.include_router(
    v1_router,
    prefix="/api/v1",
)


# ============================================================
# Root endpoint
# ============================================================

@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
    }