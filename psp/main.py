from fastapi import Depends, HTTPException,FastAPI


app = FastAPI(title="PayFlow Mock PSP")

@app.get("/health")
async def health():
    return {"status": "ok"}