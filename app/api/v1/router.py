from fastapi import APIRouter

from app.api.v1 import camera


router = APIRouter()


router.include_router(
    camera.router,
)