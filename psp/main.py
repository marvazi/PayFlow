from fastapi import Depends, HTTPException,FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from psp.db.session import get_session
from psp.api.transactions import router as transaction_router





app = FastAPI(title="PayFlow Mock PSP")

app.include_router(transaction_router)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health/db", tags=["health"])
async def check_database(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"database": "ok"}