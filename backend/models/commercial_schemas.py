"""Schemas for organization-scoped commercial workflows."""

from typing import Optional, Literal, Any

from pydantic import BaseModel, Field


OrgRole = Literal["owner", "manager", "dispatcher", "technician", "viewer"]
WorkOrderStatus = Literal[
    "draft",
    "quoted",
    "scheduled",
    "assigned",
    "pending",
    "in_progress",
    "completed",
    "verified",
    "cancelled",
]


class OrganizationSummary(BaseModel):
    id: str
    name: str
    slug: str
    personal: bool = False
    role: OrgRole


class MembershipResponse(BaseModel):
    organization_id: str
    user_id: str
    role: OrgRole
    status: str
    email: Optional[str] = None
    name: Optional[str] = None


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrganizationInviteCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: OrgRole


class OrganizationInviteResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    role: OrgRole
    status: str
    invited_by_user_id: str
    expires_at: str
    created_at: str
    accepted_at: Optional[str] = None
    accept_token: Optional[str] = None


class MembershipUpdateRequest(BaseModel):
    role: OrgRole


class OrganizationAuditLogResponse(BaseModel):
    id: int
    organization_id: str
    actor_user_id: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SetActiveOrganizationRequest(BaseModel):
    organization_id: str


class SiteCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=2000)
    customer_type: Literal["contractor", "property_manager", "mixed"] = "mixed"
    lot_id: Optional[str] = None


class SiteUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=2000)
    customer_type: Optional[Literal["contractor", "property_manager", "mixed"]] = None
    status: Optional[Literal["active", "archived"]] = None
    lot_id: Optional[str] = None


class SiteResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    address: str
    notes: str
    customer_type: str
    status: str
    lot_id: Optional[str] = None
    created_at: str
    updated_at: str
    design_name: Optional[str] = None
    center: Optional[dict[str, float]] = None
    zoom: Optional[int] = None


class SiteScanCreateRequest(BaseModel):
    site_id: str
    scan_type: Literal["satellite_import", "manual_trace", "drone_capture", "dxf_import", "telemetry_replay"] = "manual_trace"
    notes: str = Field(default="", max_length=2000)
    source_media_asset_id: Optional[str] = None


class SiteScanResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    lot_id: Optional[str] = None
    source_media_asset_id: Optional[str] = None
    scan_type: str
    notes: str
    summary: dict[str, Any] = Field(default_factory=dict)
    geometry_snapshot: list[Any] = Field(default_factory=list)
    captured_at: str
    created_at: str
    updated_at: str


class SiteSimulationCreateRequest(BaseModel):
    site_id: str
    scan_id: Optional[str] = None
    work_order_id: Optional[str] = None
    robot_id: Optional[str] = None
    mode: Literal["preview", "dispatch_readiness", "mission_rehearsal"] = "preview"
    speed_mph: float = Field(default=2.0, gt=0, le=8.0)
    notes: str = Field(default="", max_length=2000)


class SiteSimulationResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    scan_id: Optional[str] = None
    work_order_id: Optional[str] = None
    robot_id: Optional[str] = None
    status: str
    mode: str
    notes: str
    config: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class QuoteCreateRequest(BaseModel):
    site_id: str
    title: str = Field(min_length=1, max_length=200)
    cadence: str = Field(default="one-time", max_length=50)
    scope: str = Field(default="", max_length=5000)
    notes: str = Field(default="", max_length=5000)
    proposed_price: Optional[float] = Field(default=None, ge=0)
    features: Optional[list[Any]] = None


class QuoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    cadence: Optional[str] = Field(default=None, max_length=50)
    scope: Optional[str] = Field(default=None, max_length=5000)
    notes: Optional[str] = Field(default=None, max_length=5000)
    proposed_price: Optional[float] = Field(default=None, ge=0)
    status: Optional[Literal["draft", "sent", "accepted", "declined", "expired"]] = None


class QuoteResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    created_by_user_id: str
    title: str
    cadence: str
    scope: str
    notes: str
    status: str
    proposed_price: float
    total_line_length_ft: float
    paint_gallons: float
    estimated_runtime_min: int
    estimated_cost: float
    created_at: str
    updated_at: str
    site_name: Optional[str] = None


class WorkOrderCreateRequest(BaseModel):
    site_id: str
    quote_id: Optional[str] = None
    title: str = Field(min_length=1, max_length=200)
    date: str
    status: WorkOrderStatus = "scheduled"
    lot_id: Optional[str] = None
    scheduled_start_at: Optional[str] = None
    scheduled_end_at: Optional[str] = None
    assigned_robot_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    time_preference: Optional[Literal["morning", "afternoon", "evening"]] = "morning"
    notes: str = Field(default="", max_length=5000)


class WorkOrderUpdateRequest(BaseModel):
    status: Optional[WorkOrderStatus] = None
    scheduled_start_at: Optional[str] = None
    scheduled_end_at: Optional[str] = None
    assigned_robot_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    verified_at: Optional[str] = None


class JobRunCreateRequest(BaseModel):
    job_id: str
    robot_id: Optional[str] = None
    technician_user_id: Optional[str] = None
    notes: str = Field(default="", max_length=4000)


class JobRunUpdateRequest(BaseModel):
    status: Optional[Literal["started", "paused", "completed", "failed"]] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    actual_paint_gallons: Optional[float] = Field(default=None, ge=0)
    telemetry_summary: Optional[dict[str, Any]] = None


class JobRunResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    job_id: str
    robot_id: Optional[str] = None
    technician_user_id: Optional[str] = None
    status: str
    notes: str
    telemetry_summary: Optional[dict[str, Any]] = None
    actual_paint_gallons: Optional[float] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


class MediaAssetResponse(BaseModel):
    id: str
    organization_id: str
    asset_type: str
    filename: str
    content_type: str
    size_bytes: int
    site_id: Optional[str] = None
    job_id: Optional[str] = None
    job_run_id: Optional[str] = None
    report_id: Optional[str] = None
    created_at: str


class JobReportResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    job_id: str
    job_run_id: Optional[str] = None
    status: str
    report_json: dict[str, Any]
    pdf_asset_id: Optional[str] = None
    generated_at: str
    created_at: str


class MaintenanceEventCreateRequest(BaseModel):
    robot_id: str
    event_type: Literal["inspection", "repair", "battery_service", "pump_service", "nozzle_swap", "firmware_check"]
    summary: str = Field(min_length=1, max_length=500)
    details: str = Field(default="", max_length=5000)
    completed_at: Optional[str] = None


class MaintenanceEventResponse(BaseModel):
    id: str
    robot_id: str
    organization_id: Optional[str] = None
    event_type: str
    summary: str
    details: str
    completed_at: Optional[str] = None
    created_at: str


class ServiceChecklistCreateRequest(BaseModel):
    robot_id: str
    name: str = Field(min_length=1, max_length=200)
    checklist_items: list[str] = Field(default_factory=list)
    completed_at: Optional[str] = None


class ServiceChecklistResponse(BaseModel):
    id: str
    robot_id: str
    name: str
    checklist_items: list[str]
    completed_at: Optional[str] = None
    created_at: str


class ConsumableItemCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(default="unit", max_length=40)
    on_hand: float = Field(default=0, ge=0)
    reorder_level: float = Field(default=0, ge=0)


class ConsumableItemUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=40)
    on_hand: Optional[float] = Field(default=None, ge=0)
    reorder_level: Optional[float] = Field(default=None, ge=0)


class ConsumableUsageCreateRequest(BaseModel):
    consumable_item_id: str
    quantity: float = Field(gt=0)
    job_run_id: Optional[str] = None
    notes: str = Field(default="", max_length=2000)


class ConsumableItemResponse(BaseModel):
    id: str
    organization_id: str
    sku: str
    name: str
    unit: str
    on_hand: float
    reorder_level: float
    created_at: str
    updated_at: str


class ConsumableUsageResponse(BaseModel):
    id: str
    organization_id: str
    consumable_item_id: str
    quantity: float
    job_run_id: Optional[str] = None
    notes: str
    created_at: str


class RobotClaimCreateRequest(BaseModel):
    robot_id: str


class RobotClaimCommissionRequest(BaseModel):
    friendly_name: str = Field(default="", max_length=200)
    deployment_notes: str = Field(default="", max_length=2000)


class RobotClaimResponse(BaseModel):
    id: str
    robot_id: str
    organization_id: Optional[str] = None
    status: str
    commissioning_status: str
    friendly_name: str = ""
    deployment_notes: str = ""
    created_by_user_id: Optional[str] = None
    claimed_by_user_id: Optional[str] = None
    claimed_at: Optional[str] = None
    commissioned_at: Optional[str] = None
    created_at: str
    updated_at: str
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    maintenance_status: Optional[str] = None
    issue_state: Optional[str] = None
    last_seen_at: Optional[str] = None
    claim_code: Optional[str] = None
