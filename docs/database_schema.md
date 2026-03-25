# Database Schema Reference

All tables use TEXT columns for timestamps (ISO 8601 format) and TEXT UUIDs for primary keys unless noted otherwise. SQLite backend enforces `PRAGMA foreign_keys=ON` and uses WAL journal mode.

---

## Auth

### users

Primary account table for all Strype platform users.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| email | TEXT UNIQUE NOT NULL | |
| password_hash | TEXT NOT NULL | |
| name | TEXT | Default `''` |
| plan | TEXT | Default `'free'`. One of free/pro/robot/enterprise |
| active_lot_id | TEXT | Legacy pointer to last-viewed lot |
| active_organization_id | TEXT | Currently selected org context |
| map_lat, map_lng | REAL | Saved map viewport center |
| map_zoom | INTEGER | Saved map zoom level |
| is_admin | INTEGER | Platform superadmin flag (0/1) |
| stripe_customer_id | TEXT | Stripe customer reference |
| company_name | TEXT | Default `''` |
| phone | TEXT | Default `''` |
| email_verified | INTEGER | 0/1 flag |
| verification_token | TEXT | One-time email verification token |
| verification_expires_at | TEXT | Expiry for verification_token |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_users_email` on `(email)`.

### password_resets

Short-lived tokens for password reset flows. Expired rows are purged on DB init.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| token_hash | TEXT NOT NULL | Hashed reset token |
| expires_at | TEXT NOT NULL | |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_resets_token` on `(token_hash)`.

### login_attempts

Tracks failed login attempts per email for brute-force rate limiting.

| Column | Type | Notes |
|--------|------|-------|
| email | TEXT PK | Keyed by email, not user id |
| attempts | INTEGER | Default 0 |
| locked_until | TEXT | Lockout expiry (null = not locked) |
| updated_at | TEXT NOT NULL | |

### token_blocklist

Revoked JWT tokens. Checked on every authenticated request. Expired rows are purged on DB init.

| Column | Type | Notes |
|--------|------|-------|
| jti | TEXT PK | JWT ID claim |
| user_id | TEXT NOT NULL | Who the token belonged to |
| expires_at | TEXT NOT NULL | Original token expiry (for cleanup) |
| created_at | TEXT NOT NULL | When revoked |

**Indexes:** `idx_blocklist_expires` on `(expires_at)`.

### refresh_tokens

Long-lived refresh tokens for JWT rotation. Each row is a single valid refresh token.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| token_hash | TEXT NOT NULL | Hashed token value |
| expires_at | TEXT NOT NULL | |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_refresh_tokens_user` on `(user_id)`.

---

## Organizations

### organizations

Multi-tenant workspaces. Every user gets a personal org on signup; additional shared orgs can be created.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| name | TEXT NOT NULL | Display name |
| slug | TEXT UNIQUE NOT NULL | URL-safe identifier |
| personal | INTEGER | Default 0. 1 = auto-created personal workspace |
| created_by_user_id | TEXT | FK -> users(id) |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

### memberships

Join table linking users to organizations with a role. Composite unique constraint on `(organization_id, user_id)`.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| role | TEXT NOT NULL | e.g. `owner`, `admin`, `member` |
| status | TEXT | Default `'active'` |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_memberships_user` on `(user_id)`, `idx_memberships_org` on `(organization_id)`.
**Constraints:** UNIQUE `(organization_id, user_id)`.

### organization_invites

Pending invitations to join an organization. Token is hashed for storage.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| email | TEXT NOT NULL | Invitee email |
| role | TEXT NOT NULL | Role to assign on acceptance |
| token_hash | TEXT NOT NULL UNIQUE | Hashed invite token |
| status | TEXT | Default `'pending'`. Also `accepted`, `expired` |
| invited_by_user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| accepted_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| accepted_at | TEXT | |
| expires_at | TEXT NOT NULL | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_org_invites_org` on `(organization_id, status)`, `idx_org_invites_email` on `(email, status)`, `idx_org_invites_token` on `(token_hash)`.

### organization_audit_logs

Org-scoped audit trail for member actions within an organization (invites sent, roles changed, members removed, settings updated, etc.). Distinct from the platform-level `audit_logs` table, which tracks superadmin actions.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| actor_user_id | TEXT | FK -> users(id) ON DELETE SET NULL. Null if system-generated |
| action | TEXT NOT NULL | e.g. `member.invited`, `member.removed`, `role.changed` |
| target_type | TEXT | e.g. `membership`, `invite`, `organization` |
| target_id | TEXT | ID of the affected entity |
| detail_json | TEXT | Default `'{}'`. Structured context for the action |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_org_audit_org` on `(organization_id, created_at)`.

---

## Lots & Sites

### lots

A parking lot or surface area containing GeoJSON line features for striping. Soft-deletable via `deleted_at`.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE. Original creator |
| organization_id | TEXT | FK -> organizations(id) ON DELETE CASCADE. Backfilled from user |
| name | TEXT NOT NULL | |
| center_lat, center_lng | REAL NOT NULL | Map center |
| zoom | INTEGER | Default 18 |
| features | TEXT | Default `'[]'`. GeoJSON FeatureCollection as JSON string |
| deleted_at | TEXT | Soft delete timestamp. All queries filter `WHERE deleted_at IS NULL` |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_lots_user` on `(user_id)`, `idx_lots_org` on `(organization_id)`, `idx_lots_user_deleted` on `(user_id, deleted_at)`.

### sites

A named customer location within an organization. Wraps a lot with business metadata (address, customer type, notes). One-to-one relationship with a lot via the UNIQUE constraint on `lot_id`.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| lot_id | TEXT UNIQUE | FK -> lots(id) ON DELETE SET NULL. The linked lot geometry |
| name | TEXT NOT NULL | |
| address | TEXT | Default `''` |
| notes | TEXT | Default `''` |
| customer_type | TEXT | Default `'mixed'`. e.g. `commercial`, `residential`, `mixed` |
| status | TEXT | Default `'active'` |
| created_by_user_id | TEXT | FK -> users(id) |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_sites_org` on `(organization_id, status)`.

### site_scans

A point-in-time capture of a site's physical condition (pre-stripe survey, post-stripe inspection, etc.). Links to media assets (photos, ortho images) and snapshots the lot geometry at capture time. Used as input for simulation_runs to plan or preview missions.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT NOT NULL | FK -> sites(id) ON DELETE CASCADE |
| lot_id | TEXT | FK -> lots(id) ON DELETE SET NULL |
| source_media_asset_id | TEXT | FK -> media_assets(id) ON DELETE SET NULL. The uploaded image/scan file |
| scan_type | TEXT NOT NULL | e.g. `pre_stripe`, `post_stripe`, `survey` |
| notes | TEXT | Default `''` |
| summary_json | TEXT | Default `'{}'`. Extracted metrics (line count, condition, etc.) |
| geometry_snapshot_json | TEXT | Default `'[]'`. Frozen copy of lot features at scan time |
| captured_at | TEXT NOT NULL | When the scan was physically taken |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_site_scans_site` on `(site_id, captured_at)`.

### quotes

A pricing proposal for striping work at a site. Captures scope, estimated materials, runtime, and proposed price.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT NOT NULL | FK -> sites(id) ON DELETE CASCADE |
| created_by_user_id | TEXT NOT NULL | FK -> users(id) |
| title | TEXT NOT NULL | |
| cadence | TEXT | Default `'one-time'`. e.g. `monthly`, `quarterly` |
| scope | TEXT | Default `''` |
| notes | TEXT | Default `''` |
| status | TEXT | Default `'draft'`. Also `sent`, `accepted`, `declined` |
| proposed_price | REAL | Default 0 |
| total_line_length_ft | REAL | Default 0 |
| paint_gallons | REAL | Default 0 |
| estimated_runtime_min | INTEGER | Default 0 |
| estimated_cost | REAL | Default 0. Internal cost estimate |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_quotes_org` on `(organization_id, site_id)`.

---

## Jobs & Scheduling

### jobs

A single striping work order. Linked to a lot (required) and optionally to a site, quote, robot, technician, and recurring schedule. Status transitions: `pending` -> `in_progress` -> `completed`.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE. Job creator/owner |
| organization_id | TEXT | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT | FK -> sites(id) ON DELETE SET NULL |
| lot_id | TEXT NOT NULL | FK -> lots(id) ON DELETE CASCADE |
| quote_id | TEXT | FK -> quotes(id) ON DELETE SET NULL |
| date | TEXT NOT NULL | Scheduled date |
| status | TEXT | Default `'pending'` |
| time_preference | TEXT | Default `'morning'` |
| scheduled_start_at | TEXT | Planned start datetime |
| scheduled_end_at | TEXT | Planned end datetime |
| assigned_user_id | TEXT | FK -> users(id) ON DELETE SET NULL. Technician/operator |
| robot_id | TEXT | Assigned robot (not FK-constrained at table level) |
| recurring_schedule_id | TEXT | Source schedule if auto-generated |
| started_at | TEXT | Actual start |
| completed_at | TEXT | Actual completion |
| verified_at | TEXT | Post-completion verification timestamp |
| notes | TEXT | Default `''` |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_jobs_user` on `(user_id)`, `idx_jobs_org` on `(organization_id, site_id)`, `idx_jobs_lot` on `(lot_id)`, `idx_jobs_user_lot` on `(user_id, lot_id)`, `idx_jobs_recurring_schedule` on `(recurring_schedule_id)`, `idx_jobs_assigned_user` on `(assigned_user_id)`.

### job_estimates

Computed cost/material estimates for a job, derived from lot GeoJSON geometry. One-to-one with a job (UNIQUE on `job_id`).

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| job_id | TEXT UNIQUE NOT NULL | FK -> jobs(id) ON DELETE CASCADE |
| total_line_length_ft | REAL | |
| paint_gallons | REAL | |
| estimated_runtime_min | INTEGER | |
| estimated_cost | REAL | |
| created_at | TEXT NOT NULL | |

### job_runs

An execution record for a job -- one job may have multiple runs (retries, partial completions). Captures which robot and technician performed the work, actual paint usage, and a summary of telemetry from the run.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT | FK -> sites(id) ON DELETE SET NULL |
| job_id | TEXT NOT NULL | FK -> jobs(id) ON DELETE CASCADE |
| robot_id | TEXT | FK -> robots(id) ON DELETE SET NULL |
| technician_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| status | TEXT | Default `'started'`. e.g. `started`, `completed`, `aborted` |
| notes | TEXT | Default `''` |
| telemetry_summary | TEXT | Default `'{}'`. Aggregated telemetry snapshot as JSON |
| actual_paint_gallons | REAL | Measured paint consumed |
| started_at | TEXT | |
| completed_at | TEXT | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_job_runs_job` on `(job_id, created_at)`.

### recurring_schedules

Defines a repeating job pattern. A background scheduler reads active schedules and auto-creates job rows when `next_run` is reached.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| organization_id | TEXT | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT | FK -> sites(id) ON DELETE SET NULL |
| lot_id | TEXT NOT NULL | FK -> lots(id) ON DELETE CASCADE |
| frequency | TEXT NOT NULL | e.g. `weekly`, `biweekly`, `monthly` |
| day_of_week | INTEGER | 0=Monday through 6=Sunday |
| day_of_month | INTEGER | 1-31 for monthly schedules |
| time_preference | TEXT | Default `'morning'` |
| active | INTEGER | Default 1. 0 = paused |
| next_run | TEXT NOT NULL | Next date a job should be generated |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_schedules_user` on `(user_id)`, `idx_schedules_next` on `(active, next_run)`.

### simulation_runs

A virtual dry-run of a striping mission at a site. Takes a site scan's geometry snapshot (or current lot geometry) and runs pathgen simulation with robot-specific parameters. Used for mission preview, cost estimation, and path optimization before committing to a real job run. Can be linked to a job via `work_order_id` or run standalone for planning.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT NOT NULL | FK -> sites(id) ON DELETE CASCADE |
| scan_id | TEXT | FK -> site_scans(id) ON DELETE SET NULL. The scan providing input geometry |
| work_order_id | TEXT | FK -> jobs(id) ON DELETE SET NULL. Links to a real job if applicable |
| robot_id | TEXT | FK -> robots(id) ON DELETE SET NULL. Target robot hardware profile |
| status | TEXT | Default `'ready'`. e.g. `ready`, `running`, `completed`, `failed` |
| mode | TEXT | Default `'preview'`. e.g. `preview`, `full`, `optimize` |
| notes | TEXT | Default `''` |
| config_json | TEXT | Default `'{}'`. Simulation parameters (speed, paint width, overlap, etc.) |
| result_json | TEXT | Default `'{}'`. Output: path coords, estimated time, paint usage, coverage map |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_simulation_runs_site` on `(site_id, created_at)`.

**Relationship to site_scans:** A simulation_run optionally references a site_scan via `scan_id`. The scan provides the geometry snapshot and condition data that the simulation uses as input. Without a scan reference, the simulation uses the current lot geometry directly.

---

## Billing

### subscriptions

Stripe subscription state mirror. Tracks plan tier, billing period, and cancellation intent.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| stripe_customer_id | TEXT | |
| stripe_subscription_id | TEXT | |
| plan | TEXT NOT NULL | e.g. `free`, `pro`, `robot`, `enterprise` |
| status | TEXT NOT NULL | e.g. `active`, `past_due`, `canceled` |
| current_period_end | TEXT | |
| cancel_at_period_end | INTEGER | Default 0 |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_subs_user` on `(user_id)`, `idx_subs_stripe` on `(stripe_subscription_id)`.

### webhook_events

Stripe webhook idempotency guard. Stores processed event IDs to prevent duplicate handling.

| Column | Type | Notes |
|--------|------|-------|
| event_id | TEXT PK | Stripe event ID |
| processed_at | TEXT NOT NULL | |

### waitlist

Pre-launch email capture for interested users.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| email | TEXT NOT NULL | |
| source | TEXT | Default `'landing'` |
| created_at | TEXT NOT NULL | |

---

## Fleet & Robots

### robots

Physical robot units in the fleet. Tracks hardware/firmware versions, connectivity status, and maintenance state.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| serial_number | TEXT UNIQUE NOT NULL | |
| status | TEXT | Default `'available'`. e.g. `available`, `assigned`, `maintenance`, `retired` |
| hardware_version | TEXT | Default `'v1'` |
| firmware_version | TEXT | |
| api_key | TEXT | Robot-to-cloud auth key |
| api_key_last4 | TEXT | Display hint for key identification |
| last_seen_at | TEXT | Last heartbeat timestamp |
| last_battery_pct | INTEGER | |
| last_state | TEXT | e.g. `idle`, `striping`, `returning` |
| maintenance_status | TEXT | Default `'ready'`. e.g. `ready`, `due`, `overdue` |
| battery_health_pct | INTEGER | Long-term battery degradation metric |
| service_due_at | TEXT | Next scheduled service date |
| last_successful_mission_at | TEXT | |
| issue_state | TEXT | Default `''`. Current issue flag if any |
| notes | TEXT | Default `''` |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

### robot_assignments

Shipping lifecycle for a robot sent to a customer. Tracks outbound and return shipment status.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| robot_id | TEXT NOT NULL | FK -> robots(id) |
| user_id | TEXT NOT NULL | FK -> users(id) ON DELETE CASCADE |
| status | TEXT | Default `'preparing'`. e.g. `preparing`, `shipped`, `delivered`, `returning`, `returned` |
| tracking_number | TEXT | Outbound tracking |
| shipped_at | TEXT | |
| delivered_at | TEXT | |
| return_tracking | TEXT | Return shipment tracking |
| returned_at | TEXT | |
| label_url | TEXT | Outbound shipping label |
| return_label_url | TEXT | Return shipping label |
| ship_to_address | TEXT | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_assignments_user` on `(user_id)`, `idx_assignments_robot` on `(robot_id)`, `idx_assignments_robot_status` on `(robot_id, status)`.

### robot_claims

Self-service robot provisioning. An admin creates a claim code for a robot; a customer redeems it to bind the robot to their organization. Tracks commissioning status through the onboarding flow.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| robot_id | TEXT NOT NULL | FK -> robots(id) ON DELETE CASCADE |
| organization_id | TEXT | FK -> organizations(id) ON DELETE SET NULL. Set on claim |
| claim_code_hash | TEXT NOT NULL UNIQUE | Hashed claim code |
| status | TEXT | Default `'pending'`. e.g. `pending`, `claimed`, `revoked` |
| commissioning_status | TEXT | Default `'unclaimed'`. e.g. `unclaimed`, `claimed`, `commissioned` |
| friendly_name | TEXT | Default `''`. Customer-assigned robot name |
| deployment_notes | TEXT | Default `''` |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL. Admin who created the code |
| claimed_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL. User who redeemed the code |
| claimed_at | TEXT | |
| commissioned_at | TEXT | |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_robot_claims_robot` on `(robot_id, status)`, `idx_robot_claims_org` on `(organization_id, status)`, `idx_robot_claims_code` on `(claim_code_hash)`, `idx_robot_claims_claimed_by` on `(claimed_by_user_id)`.

### maintenance_events

Service history log for a robot. Each row is a discrete maintenance action (oil change, nozzle replacement, firmware update, etc.).

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| robot_id | TEXT NOT NULL | FK -> robots(id) ON DELETE CASCADE |
| organization_id | TEXT | FK -> organizations(id) ON DELETE SET NULL |
| event_type | TEXT NOT NULL | e.g. `scheduled`, `repair`, `firmware_update`, `inspection` |
| summary | TEXT NOT NULL | Short description |
| details | TEXT | Default `''`. Extended notes |
| completed_at | TEXT | Null if still in progress |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_maintenance_robot` on `(robot_id, created_at)`.

### service_checklists

Reusable maintenance checklists for robots. Stores checklist items as a JSON array.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| robot_id | TEXT NOT NULL | FK -> robots(id) ON DELETE CASCADE |
| organization_id | TEXT | FK -> organizations(id) ON DELETE SET NULL |
| name | TEXT NOT NULL | Checklist title |
| checklist_json | TEXT | Default `'[]'`. Array of checklist items with completion state |
| completed_at | TEXT | Null until all items checked |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |

---

## Telemetry

### robot_telemetry

Time-series heartbeat data from robots in the field. Written by robots via the telemetry endpoint (X-Robot-Key auth). High-volume append-only table.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| robot_id | TEXT NOT NULL | FK -> robots(id) |
| battery_pct | INTEGER | |
| lat, lng | REAL | GPS position |
| state | TEXT | e.g. `idle`, `striping`, `paused`, `error` |
| paint_level_pct | INTEGER | Estimated paint remaining |
| error_code | TEXT | Current error if any |
| rssi | INTEGER | Cellular/WiFi signal strength |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_telemetry_robot` on `(robot_id, created_at)`, `idx_telemetry_created` on `(created_at)`.

---

## Media & Reports

### media_assets

File uploads (photos, PDFs, ortho images, DXF/SVG imports) associated with org resources. Storage-agnostic via `storage_backend` and `storage_key`.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT | FK -> sites(id) ON DELETE SET NULL |
| job_id | TEXT | FK -> jobs(id) ON DELETE SET NULL |
| job_run_id | TEXT | FK -> job_runs(id) ON DELETE SET NULL |
| report_id | TEXT | Logical link to a job_report |
| asset_type | TEXT NOT NULL | e.g. `photo`, `scan`, `dxf`, `svg`, `pdf` |
| filename | TEXT NOT NULL | Original upload filename |
| storage_backend | TEXT | Default `'local'`. e.g. `local`, `s3` |
| storage_key | TEXT NOT NULL | Path or object key in the storage backend |
| content_type | TEXT | Default `'application/octet-stream'` |
| size_bytes | INTEGER | Default 0 |
| uploaded_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_media_assets_job` on `(job_id, job_run_id)`.

### job_reports

Generated completion reports for jobs. Contains structured report data as JSON and optionally a rendered PDF.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| site_id | TEXT NOT NULL | FK -> sites(id) ON DELETE CASCADE |
| job_id | TEXT NOT NULL | FK -> jobs(id) ON DELETE CASCADE |
| job_run_id | TEXT | FK -> job_runs(id) ON DELETE SET NULL |
| status | TEXT | Default `'generated'` |
| report_json | TEXT NOT NULL | Structured report content |
| pdf_asset_id | TEXT | FK -> media_assets(id) ON DELETE SET NULL. Rendered PDF |
| generated_at | TEXT NOT NULL | |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_reports_job` on `(job_id)`.

---

## Operations

### consumables_inventory

Tracks stock levels of consumable materials (paint, nozzles, tape, etc.) per organization.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| sku | TEXT NOT NULL | Product SKU |
| name | TEXT NOT NULL | |
| unit | TEXT | Default `'unit'`. e.g. `gallon`, `nozzle`, `roll` |
| on_hand | REAL | Default 0. Current quantity |
| reorder_level | REAL | Default 0. Threshold for reorder alert |
| created_at | TEXT NOT NULL | |
| updated_at | TEXT NOT NULL | |

**Indexes:** `idx_consumables_org` on `(organization_id)`.

### consumable_usage

Deduction records against consumables_inventory. Optionally linked to a job_run for per-job material tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| organization_id | TEXT NOT NULL | FK -> organizations(id) ON DELETE CASCADE |
| consumable_item_id | TEXT NOT NULL | FK -> consumables_inventory(id) ON DELETE CASCADE |
| job_run_id | TEXT | FK -> job_runs(id) ON DELETE SET NULL |
| quantity | REAL NOT NULL | Amount consumed |
| notes | TEXT | Default `''` |
| created_by_user_id | TEXT | FK -> users(id) ON DELETE SET NULL |
| created_at | TEXT NOT NULL | |

### audit_logs

Platform-level superadmin audit trail. Records actions taken by platform admins (user management, plan changes, system configuration). This is distinct from `organization_audit_logs`, which tracks member actions within a specific organization.

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK AUTOINCREMENT | |
| admin_email | TEXT NOT NULL | The admin who performed the action |
| action | TEXT NOT NULL | e.g. `user.delete`, `plan.override`, `robot.create` |
| target | TEXT | Identifier of the affected entity |
| detail | TEXT | Free-form context |
| created_at | TEXT NOT NULL | |

---

## Email

### email_events

SendGrid webhook event log for email deliverability tracking. Stores bounce, open, click, spam report, and other email lifecycle events. The `sg_event_id` UNIQUE constraint provides idempotent webhook processing.

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | UUID |
| email | TEXT NOT NULL | Recipient address |
| event_type | TEXT NOT NULL | e.g. `delivered`, `bounce`, `open`, `click`, `spam_report`, `dropped` |
| reason | TEXT | Default `''`. Bounce/drop reason from SendGrid |
| sg_event_id | TEXT UNIQUE | SendGrid event ID for deduplication |
| sg_message_id | TEXT | Default `''`. SendGrid message ID for correlation |
| created_at | TEXT NOT NULL | |

**Indexes:** `idx_email_events_email` on `(email, event_type)`, `idx_email_events_sg` on `(sg_event_id)`.
