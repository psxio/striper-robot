"""Organization and membership routes."""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_current_user
from ..models.commercial_schemas import (
    MembershipResponse,
    MembershipUpdateRequest,
    OrganizationAuditLogResponse,
    OrganizationCreateRequest,
    OrganizationInviteCreateRequest,
    OrganizationInviteResponse,
    SetActiveOrganizationRequest,
)
from ..orgs import require_organization_role
from ..rate_limit import limiter
from ..services import organization_audit_store, organization_store, user_store
from ..shared import user_to_response

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.get("")
async def list_organizations(user: dict = Depends(get_current_user)):
    items = await organization_store.list_user_organizations(user["id"])
    return {"items": items, "active_organization_id": user.get("active_organization_id")}


@router.post("", status_code=201)
async def create_organization(
    body: OrganizationCreateRequest,
    user: dict = Depends(get_current_user),
):
    organization = await organization_store.create_organization(body.name, user["id"], personal=False)
    membership = await organization_store.get_membership(organization["id"], user["id"])
    await organization_audit_store.log_event(
        organization["id"],
        "organization.created",
        actor_user_id=user["id"],
        target_type="organization",
        target_id=organization["id"],
        detail={"name": organization["name"]},
    )
    return {"organization": organization, "membership": membership}


@router.post("/active")
async def set_active_organization(
    body: SetActiveOrganizationRequest,
    user: dict = Depends(get_current_user),
):
    changed = await organization_store.set_active_organization(user["id"], body.organization_id)
    if not changed:
        raise HTTPException(status_code=404, detail="Organization not found")
    refreshed = await user_store.get_user_by_id(user["id"]) or dict(user)
    refreshed["active_organization_id"] = body.organization_id
    return await user_to_response(refreshed)


@router.get("/memberships")
async def list_memberships(context: dict = Depends(require_organization_role("manager"))):
    items = await organization_store.list_memberships(context["organization"]["id"])
    return {"items": items, "organization_id": context["organization"]["id"]}


@router.post("/invites", response_model=OrganizationInviteResponse, status_code=201)
@limiter.limit("10/minute")
async def create_invite(
    request: Request,
    body: OrganizationInviteCreateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    try:
        invite = await organization_store.create_invite(
            context["organization"]["id"],
            context["user"]["id"],
            body.email,
            body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "membership.invited",
        actor_user_id=context["user"]["id"],
        target_type="invite",
        target_id=invite["id"],
        detail={"email": invite["email"], "role": invite["role"]},
    )
    return OrganizationInviteResponse(**invite)


@router.get("/invites")
async def list_invites(context: dict = Depends(require_organization_role("manager"))):
    items = await organization_store.list_pending_invites(context["organization"]["id"])
    return {"items": [OrganizationInviteResponse(**item) for item in items], "total": len(items)}


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, user: dict = Depends(get_current_user)):
    try:
        invite = await organization_store.accept_invite(token, user["id"], user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    membership = await organization_store.get_membership(invite["organization_id"], user["id"])
    await organization_audit_store.log_event(
        invite["organization_id"],
        "membership.accepted",
        actor_user_id=user["id"],
        target_type="membership",
        target_id=user["id"],
        detail={"email": user["email"], "role": membership["role"] if membership else None},
    )
    refreshed = await user_store.get_user_by_id(user["id"]) or user
    return {
        "invite": OrganizationInviteResponse(**invite),
        "membership": MembershipResponse(**membership) if membership else None,
        "user": await user_to_response(refreshed),
    }


@router.patch("/memberships/{target_user_id}", response_model=MembershipResponse)
async def update_membership(
    target_user_id: str,
    body: MembershipUpdateRequest,
    context: dict = Depends(require_organization_role("owner")),
):
    try:
        membership = await organization_store.update_membership_role(
            context["organization"]["id"],
            target_user_id,
            body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "membership.role_changed",
        actor_user_id=context["user"]["id"],
        target_type="membership",
        target_id=target_user_id,
        detail={"role": body.role},
    )
    return MembershipResponse(**membership)


@router.delete("/memberships/{target_user_id}")
async def delete_membership(
    target_user_id: str,
    context: dict = Depends(require_organization_role("owner")),
):
    try:
        deleted = await organization_store.remove_membership(
            context["organization"]["id"],
            target_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Membership not found")
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "membership.removed",
        actor_user_id=context["user"]["id"],
        target_type="membership",
        target_id=target_user_id,
        detail={},
    )
    return {"ok": True}


@router.get("/audit-logs")
async def list_audit_logs(context: dict = Depends(require_organization_role("manager"))):
    items = await organization_audit_store.list_events(context["organization"]["id"])
    return {"items": [OrganizationAuditLogResponse(**item) for item in items], "total": len(items)}
