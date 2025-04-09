from fastapi import APIRouter
from app.api.endpoints import health
from app.api.endpoints import user

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(health.router, prefix="/api/v1/user", tags=["user"])
