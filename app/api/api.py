from fastapi import APIRouter
from app.api.endpoints import health, user, cart, category, product, review, promotion

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(user.router, prefix="/api/v1/user", tags=["user"])
api_router.include_router(category.router, prefix="/api/v1/category", tags=["category"])
api_router.include_router(product.router, prefix="/api/v1/product", tags=["product"])
api_router.include_router(cart.router, prefix="/api/v1/cart", tags=["cart"])
api_router.include_router(review.router, prefix="/api/v1/review", tags=["review"])
api_router.include_router(promotion.router, prefix="/api/v1/promotion", tags=["promotion"])
