"""Waitlist route -- no auth required."""

from fastapi import APIRouter, Request

from ..models.schemas import WaitlistRequest
from ..rate_limit import limiter
from ..services import waitlist_store

router = APIRouter(prefix="/api", tags=["waitlist"])


@router.post("/waitlist", status_code=201)
@limiter.limit("10/minute")
async def add_to_waitlist(request: Request, body: WaitlistRequest):
    await waitlist_store.add_to_waitlist(body.email, body.source)
    return {"ok": True}
