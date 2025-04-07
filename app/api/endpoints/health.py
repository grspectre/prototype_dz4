from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from sqlalchemy.sql import text

router = APIRouter()

@router.get("/")
async def health_check():
    return {"status": "ok"}

@router.get("/db")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "Database connection established"}
    except Exception as e:
        return {"status": "Database connection failed", "details": str(e)}
