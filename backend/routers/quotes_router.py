"""Organization-scoped quote routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..models.commercial_schemas import QuoteCreateRequest, QuoteResponse, QuoteUpdateRequest
from ..orgs import get_organization_context, require_organization_role
from ..services import organization_audit_store, quote_store, site_store

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


async def _load_site_features(organization_id: str, site_id: str) -> list[dict]:
    site = await site_store.get_site(organization_id, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    if not site.get("lot_id"):
        return []
    async for db in get_db():
        cursor = await db.execute(
            "SELECT features FROM lots WHERE id = ? AND organization_id = ?",
            (site["lot_id"], organization_id),
        )
        row = await cursor.fetchone()
        if not row:
            return []
        return json.loads(row["features"] or "[]")
    return []


@router.get("")
async def list_quotes(
    site_id: str | None = Query(default=None),
    context: dict = Depends(get_organization_context),
):
    items = await quote_store.list_quotes(context["organization"]["id"], site_id=site_id)
    return {"items": [QuoteResponse(**item) for item in items], "total": len(items)}


@router.post("", response_model=QuoteResponse, status_code=201)
async def create_quote(
    body: QuoteCreateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    site = await site_store.get_site(context["organization"]["id"], body.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    features = body.features if body.features is not None else await _load_site_features(
        context["organization"]["id"],
        body.site_id,
    )
    quote = await quote_store.create_quote(
        context["organization"]["id"],
        body.site_id,
        context["user"]["id"],
        body.title,
        body.cadence,
        body.scope,
        body.notes,
        body.proposed_price,
        features,
    )
    await organization_audit_store.log_event(
        context["organization"]["id"],
        "quote.created",
        actor_user_id=context["user"]["id"],
        target_type="quote",
        target_id=quote["id"],
        detail={"site_id": quote["site_id"], "title": quote["title"]},
    )
    return QuoteResponse(**quote)


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(quote_id: str, context: dict = Depends(get_organization_context)):
    quote = await quote_store.get_quote(context["organization"]["id"], quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return QuoteResponse(**quote)


@router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: str,
    body: QuoteUpdateRequest,
    context: dict = Depends(require_organization_role("manager")),
):
    existing = await quote_store.get_quote(context["organization"]["id"], quote_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote = await quote_store.update_quote(
        context["organization"]["id"],
        quote_id,
        title=body.title,
        cadence=body.cadence,
        scope=body.scope,
        notes=body.notes,
        proposed_price=body.proposed_price,
        status=body.status,
    )
    if body.status is not None and body.status != existing.get("status"):
        await organization_audit_store.log_event(
            context["organization"]["id"],
            "quote.status_changed",
            actor_user_id=context["user"]["id"],
            target_type="quote",
            target_id=quote_id,
            detail={"from": existing.get("status"), "to": body.status},
        )
    return QuoteResponse(**quote)
