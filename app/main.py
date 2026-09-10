from fastapi import FastAPI
from fastapi import Depends
from sqlalchemy import text

from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession


app = FastAPI(title="PayFlow")

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}

@app.get("/health/db", tags=["health"])
async def check_database(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"database": "ok"}