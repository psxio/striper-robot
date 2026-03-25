"""Robot claim and commissioning routes."""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_admin_user, require_active_billing
from ..config import settings
from ..services import email_service
from ..models.commercial_schemas import (
    RobotClaimCommissionRequest,
    RobotClaimCreateRequest,
    RobotClaimResponse,
)
from ..orgs import get_organization_context, require_organization_role
from ..services import organization_audit_store, robot_store

router = APIRouter(prefix="/api/robot-claims", tags=["robot-claims"])


@router.post("", response_model=RobotClaimResponse, status_code=201)
async def create_robot_claim(
    body: RobotClaimCreateRequest,
    admin: dict = Depends(get_admin_user),
):
    try:
        claim, code = await robot_store.create_robot_claim(body.robot_id, admin["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    claim["claim_code"] = code
    return RobotClaimResponse(**claim)


@router.get("/{code}", response_model=RobotClaimResponse)
async def validate_robot_claim(
    code: str,
    context: dict = Depends(get_organization_context),
):
    claim = await robot_store.get_claim_by_code(code)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim code not found")
    if claim["status"] == "claimed" and claim.get("organization_id") != context["organization"]["id"]:
        raise HTTPException(status_code=403, detail="Claim code belongs to another organization")
    return RobotClaimResponse(**claim)


@router.post("/{code}/claim")
async def claim_robot(
    code: str,
    body: RobotClaimCommissionRequest,
    _billing=Depends(require_active_billing),
    context: dict = Depends(require_organization_role("dispatcher")),
):
    # Enforce robot tier limits: count existing claimed robots for this org
    user = context["user"]
    plan = user.get("plan") or "free"
    limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
    max_robots = limits.get("robots", 0)
    org_id = context["organization"]["id"]
    existing_robots = await robot_store.list_claimed_robots(org_id)
    if len(existing_robots) >= max_robots:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan allows {max_robots} robot"
                   + ("s" if max_robots != 1 else "")
                   + f". Upgrade to add more.",
        )

    try:
        claim = await robot_store.claim_robot_for_organization(
            code,
            org_id,
            user["id"],
            friendly_name=body.friendly_name,
            deployment_notes=body.deployment_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await organization_audit_store.log_event(
        context["organization"]["id"],
        "fleet.robot_claimed",
        actor_user_id=context["user"]["id"],
        target_type="robot",
        target_id=claim["robot_id"],
        detail={
            "friendly_name": body.friendly_name,
            "commissioning_status": claim["commissioning_status"],
        },
    )

    # Send claim confirmation email
    import asyncio
    robot = claim.get("robot") or {}
    asyncio.create_task(email_service.send_claim_confirmation_email(
        user["email"],
        robot.get("serial_number") or claim.get("robot_id", ""),
        body.friendly_name,
    ))

    return claim
