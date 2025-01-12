from fastapi import APIRouter
from datetime import datetime
import asyncio

router = APIRouter()


@router.post("/callback/test")
async def test_callback(payload: dict):
    await asyncio.sleep(0.1)
    return {
        "status": "success",
        "message": "Test callback received",
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload
    }


@router.get("/health")
async def health_check():
    await asyncio.sleep(0.1)
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "scheduler": "running",
            "database": "connected"
        }
    }
