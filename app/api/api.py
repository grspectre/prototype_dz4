from fastapi import APIRouter
from app.api.endpoints import health
from app.api.endpoints import user
from app.api.endpoints import score

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(user.router, prefix="/api/v1/user", tags=["user"])
api_router.include_router(score.router, prefix="/api/v1/score", tags=["score"])
