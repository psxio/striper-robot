"""Background task for processing recurring schedules."""

import asyncio
import logging
from datetime import datetime, timezone

from ..config import settings
from . import email_service, job_store, schedule_store, site_store, user_store

logger = logging.getLogger("strype.scheduler")
_scheduler_state = {
    "running": False,
    "last_tick_started_at": None,
    "last_tick_completed_at": None,
    "last_error": None,
}


async def _create_due_work_item(schedule: dict, max_jobs: int) -> dict | None:
    """Create the next due work item for a schedule.

    Organization-scoped schedules generate work orders. Legacy personal schedules
    still fall back to the older job path.
    """
    if schedule.get("organization_id") and schedule.get("site_id"):
        existing = await job_store.find_work_order_for_schedule(
            schedule["organization_id"],
            schedule["id"],
            schedule["next_run"],
        )
        if existing:
            return existing
        site = await site_store.get_site(schedule["organization_id"], schedule["site_id"])
        if not site:
            raise ValueError(f"Missing site {schedule['site_id']} for recurring schedule")
        return await job_store.create_work_order(
            schedule["organization_id"],
            schedule["user_id"],
            schedule["site_id"],
            f"{site['name']} recurring service",
            schedule["next_run"],
            "scheduled",
            time_preference=schedule.get("time_preference") or "morning",
            lot_id=schedule["lot_id"],
            notes="Generated automatically from recurring schedule",
            recurring_schedule_id=schedule["id"],
        )

    return await job_store.create_job_atomic(
        schedule["user_id"],
        schedule["lot_id"],
        schedule["next_run"],
        max_jobs=max_jobs,
        time_preference=schedule.get("time_preference") or "morning",
        recurring_schedule_id=schedule["id"],
    )


async def process_due_schedules() -> int:
    """Fetch all due schedules, create jobs/work orders, and advance each schedule."""
    due = await schedule_store.get_due_schedules()
    processed = 0

    for schedule in due:
        try:
            user = await user_store.get_user_by_id(schedule["user_id"])
            if not user:
                logger.warning(
                    "Schedule %s references deleted user %s, skipping",
                    schedule["id"], schedule["user_id"],
                )
                await schedule_store.advance_schedule(schedule["id"])
                continue

            plan = user.get("plan") or "free"
            limits = settings.PLAN_LIMITS.get(plan, settings.PLAN_LIMITS["free"])
            max_jobs = limits.get("max_jobs", 5)

            job = await _create_due_work_item(schedule, max_jobs)
            if job is None:
                logger.warning(
                    "Schedule %s skipped: user %s at job limit (plan=%s, max=%d)",
                    schedule["id"], schedule["user_id"], plan, max_jobs,
                )
                await schedule_store.advance_schedule(schedule["id"])
                continue

            await schedule_store.advance_schedule(schedule["id"])
            logger.info(
                "Processed schedule %s and created due work item for lot %s (user %s)",
                schedule["id"],
                schedule["lot_id"],
                schedule["user_id"],
            )
            processed += 1

            # Notify user about auto-created job (fire-and-forget)
            lot_name = job.get("lot_name") or schedule.get("lot_id", "")
            asyncio.create_task(
                email_service.send_job_created_email(user["email"], lot_name, schedule["next_run"])
            )
        except Exception:
            logger.exception("Failed to process schedule %s", schedule["id"])

    return processed


async def run_scheduler_loop() -> None:
    """Run an infinite loop that processes due schedules every 60 seconds."""
    logger.info("Scheduler loop started")
    _scheduler_state["running"] = True
    while True:
        try:
            _scheduler_state["last_tick_started_at"] = datetime.now(timezone.utc).isoformat()
            count = await process_due_schedules()
            if count:
                logger.info("Scheduler tick: processed %d schedule(s)", count)
            _scheduler_state["last_tick_completed_at"] = datetime.now(timezone.utc).isoformat()
            _scheduler_state["last_error"] = None
        except Exception:
            _scheduler_state["last_error"] = datetime.now(timezone.utc).isoformat()
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(60)


def get_scheduler_health() -> dict:
    return dict(_scheduler_state)
