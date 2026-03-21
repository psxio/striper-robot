"""Organization-scoped auth helpers."""

from fastapi import Depends, HTTPException, Request

from .auth import get_current_user
from .services import organization_store

ROLE_PRIORITY = {
    "viewer": 0,
    "technician": 1,
    "dispatcher": 2,
    "manager": 3,
    "owner": 4,
}


async def get_organization_context(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    organization_id = request.headers.get("X-Organization-ID") or user.get("active_organization_id")
    if not organization_id:
        organization_id = await organization_store.get_default_organization_id(user["id"])
        if not organization_id:
            raise HTTPException(status_code=403, detail="No organization available")
    membership = await organization_store.get_membership(organization_id, user["id"])
    if not membership:
        raise HTTPException(status_code=403, detail="Organization access denied")
    organization = await organization_store.get_organization(organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "user": user,
        "organization": organization,
        "membership": membership,
        "role": membership["role"],
    }


def require_organization_role(min_role: str):
    async def dependency(context: dict = Depends(get_organization_context)) -> dict:
        current = ROLE_PRIORITY.get(context["role"], -1)
        required = ROLE_PRIORITY.get(min_role, 0)
        if current < required:
            raise HTTPException(status_code=403, detail=f"{min_role.title()} role required")
        return context

    return dependency
