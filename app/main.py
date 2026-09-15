from fastapi import FastAPI
from fastapi import Depends
from sqlalchemy import text
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth import router as auth_router
from app.api.organization import router as organization_router

app = FastAPI(title="PayFlow")
app.include_router(auth_router)
app.include_router(organization_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}

@app.get("/health/db", tags=["health"])
async def check_database(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"database": "ok"}

