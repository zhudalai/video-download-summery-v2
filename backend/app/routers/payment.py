from fastapi import APIRouter

router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.get("/health")
async def payment_health():
    return {"status": "payment module ready"}
