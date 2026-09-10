import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
async def health_check() -> dict:
    """Check the health status of the API."""
    logger.info("Health check endpoint called")
    return {"status": "ok"}
