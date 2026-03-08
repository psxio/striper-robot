"""Cost estimation routes."""

import logging

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models.schemas import EstimateRequest, EstimateResponse
from ..services import estimate_store

router = APIRouter(prefix="/api/estimates", tags=["estimates"])
logger = logging.getLogger("strype.estimates")


@router.post("/calculate", response_model=EstimateResponse)
async def calculate_estimate(
    body: EstimateRequest, user: dict = Depends(get_current_user)
):
    """Calculate cost estimate from lot features."""
    result = estimate_store.calculate_estimate(body.features)
    return result
