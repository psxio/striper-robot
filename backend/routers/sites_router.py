"""Organization-scoped site portfolio routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..models.commercial_schemas import SiteCreateRequest, SiteResponse, SiteUpdateRequest
from ..orgs import get_organization_context, require_organization_role
from ..services import site_store

router = APIRouter(prefix="/api/sites", tags=["sites"])


async def _validate_lot_for_org(organization_id: str, lot_id: str) -> bool:
    async for db in get_db():
        cursor = await db.execute(
            "SELECT 1 FROM lots WHERE id = ? AND organization_id = ? AND deleted_at IS NULL",
            (lot_id, organization_id),
        )
        return await cursor.fetchone() is not None
    return False


@router.get("")
async def list_sites(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    context: dict = Depends(get_organization_context),
):
    items, total = await site_store.list_sites(
        context["organization"]["id"],
        page=page,
        limit=limit,
    )
    return {"items": [SiteResponse(**item) for item in items], "total": total, "page": page, "limit": limit}


@router.post("", response_model=SiteResponse, status_code=201)
async def create_site(
    body: SiteCreateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    if body.lot_id and not await _validate_lot_for_org(context["organization"]["id"], body.lot_id):
        raise HTTPException(status_code=404, detail="Design lot not found")
    site = await site_store.create_site(
        context["organization"]["id"],
        context["user"]["id"],
        body.name,
        address=body.address,
        notes=body.notes,
        customer_type=body.customer_type,
        lot_id=body.lot_id,
    )
    return SiteResponse(**site)


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(site_id: str, context: dict = Depends(get_organization_context)):
    site = await site_store.get_site(context["organization"]["id"], site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteResponse(**site)


@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: str,
    body: SiteUpdateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    if body.lot_id and not await _validate_lot_for_org(context["organization"]["id"], body.lot_id):
        raise HTTPException(status_code=404, detail="Design lot not found")
    site = await site_store.update_site(
        context["organization"]["id"],
        site_id,
        name=body.name,
        address=body.address,
        notes=body.notes,
        customer_type=body.customer_type,
        status=body.status,
        lot_id=body.lot_id,
    )
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteResponse(**site)


@router.delete("/{site_id}")
async def delete_site(site_id: str, context: dict = Depends(require_organization_role("manager"))):
    deleted = await site_store.delete_site(context["organization"]["id"], site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"ok": True}
