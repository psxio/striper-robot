"""Background task for processing recurring schedules."""

import asyncio
import logging
from datetime import datetime, timezone
from . import schedule_store, job_store

logger = logging.getLogger("strype.scheduler")


async def process_due_schedules() -> int:
    """Fetch all due schedules, create jobs for them, and advance each schedule.

    Returns the number of schedules successfully processed.
    Individual failures are logged and skipped so one bad schedule
    does not block the others.
    """
    due = await schedule_store.get_due_schedules()
    processed = 0

    for schedule in due:
        try:
            await job_store.create_job(
                schedule["user_id"],
                schedule["lot_id"],
                schedule["next_run"],
            )
            await schedule_store.advance_schedule(schedule["id"])
            logger.info(
                "Processed schedule %s — created job for lot %s (user %s)",
                schedule["id"],
                schedule["lot_id"],
                schedule["user_id"],
            )
            processed += 1
        except Exception:
            logger.exception(
                "Failed to process schedule %s", schedule["id"]
            )

    return processed


async def run_scheduler_loop() -> None:
    """Run an infinite loop that processes due schedules every 60 seconds."""
    logger.info("Scheduler loop started")
    while True:
        try:
            count = await process_due_schedules()
            if count:
                logger.info("Scheduler tick: processed %d schedule(s)", count)
        except Exception:
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(60)
