"""
Background scheduler for automated insight generation.
Uses APScheduler for async scheduled jobs.

Jobs:
  - Daily at midnight: check reward expiry for all accounts
  - 1st of each month at 08:00: generate monthly report for previous month
  - On-demand: triggered after new statement is saved
"""
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Dhaka")
    return _scheduler


def start_scheduler():
    """Start the scheduler with all registered jobs."""
    scheduler = get_scheduler()

    if scheduler.running:
        return

    # Job 1: Daily reward expiry check (midnight Dhaka time)
    scheduler.add_job(
        _daily_reward_check,
        trigger=CronTrigger(hour=0, minute=0, timezone="Asia/Dhaka"),
        id="daily_reward_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Job 2: Monthly report generation (1st of each month, 08:00 Dhaka time)
    scheduler.add_job(
        _monthly_report_job,
        trigger=CronTrigger(day=1, hour=8, minute=0, timezone="Asia/Dhaka"),
        id="monthly_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # Job 3: Monthly AI advisor report (1st of each month, 09:00 Dhaka time)
    scheduler.add_job(
        _monthly_advisor_report_job,
        trigger=CronTrigger(day=1, hour=9, minute=0, timezone="Asia/Dhaka"),
        id="monthly_advisor_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("Scheduler started with jobs: daily_reward_check, monthly_report, monthly_advisor_report")


def stop_scheduler():
    """Stop the scheduler on app shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def trigger_post_upload_analysis(statement_id: int, period_from: date, period_to: date):
    """
    Trigger analysis immediately after a new statement is saved.
    Called by StatementService after successful upload.
    Non-blocking — schedules a one-time job.
    """
    scheduler = get_scheduler()
    if not scheduler.running:
        return

    job_id = f"post_upload_{statement_id}"
    scheduler.add_job(
        _run_post_upload_analysis,
        args=[statement_id, period_from, period_to],
        id=job_id,
        replace_existing=True,
    )
    logger.info(f"Scheduled post-upload analysis for statement {statement_id}")


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

async def _daily_reward_check():
    """Check all accounts for expiring reward points."""
    logger.info("Running daily reward expiry check")
    try:
        from app.database import AsyncSessionLocal
        from app.services.advisor import AdvisorService

        async with AsyncSessionLocal() as db:
            advisor = AdvisorService(db)
            insights = await advisor._check_reward_expiry()
            logger.info(f"Reward check: {len(insights)} alerts generated")
    except Exception as e:
        logger.error(f"Daily reward check failed: {e}")


async def _monthly_report_job():
    """Generate monthly report for the previous calendar month."""
    today = date.today()
    period_to = today.replace(day=1) - timedelta(days=1)  # Last day of prev month
    period_from = period_to.replace(day=1)                # First day of prev month

    logger.info(f"Generating monthly report for {period_from} – {period_to}")
    try:
        from app.database import AsyncSessionLocal
        from app.services.advisor import AdvisorService

        async with AsyncSessionLocal() as db:
            advisor = AdvisorService(db)
            # Generate full analysis for all accounts
            insights = await advisor.analyze_period(period_from, period_to, account_id=None)
            logger.info(f"Monthly report job: {len(insights)} insights generated")
    except Exception as e:
        logger.error(f"Monthly report job failed: {e}")


async def _monthly_advisor_report_job():
    """Generate the monthly AI advisor report for the previous calendar month."""
    today = date.today()
    prev = today.replace(day=1) - timedelta(days=1)
    year = prev.year
    month = prev.month

    logger.info(f"Generating monthly advisor report for {year}-{month:02d}")
    try:
        from app.database import AsyncSessionLocal
        from app.services.advisor import AdvisorService

        async with AsyncSessionLocal() as db:
            advisor = AdvisorService(db)
            report = await advisor.generate_advisor_report(year, month, account_id=None)
            if report:
                logger.info(
                    f"Advisor report generated: score={report.score}, "
                    f"personality={report.personality_type}"
                )
            else:
                logger.warning(f"No advisor report generated for {year}-{month:02d} (no data?)")
    except Exception as e:
        logger.error(f"Monthly advisor report job failed: {e}")


async def _run_post_upload_analysis(statement_id: int, period_from: date, period_to: date):
    """Run quick analysis after a statement upload (no monthly report, just alerts)."""
    logger.info(f"Running post-upload analysis for statement {statement_id}")
    try:
        from app.database import AsyncSessionLocal
        from app.services.advisor import AdvisorService

        async with AsyncSessionLocal() as db:
            advisor = AdvisorService(db)
            # Run only the fast, token-free insights
            insights = []
            insights.extend(await advisor._detect_overspending(period_from, period_to, None))
            insights.extend(await advisor._check_reward_expiry())
            insights.extend(await advisor._check_budget_breaches(period_from, period_to))
            logger.info(
                f"Post-upload analysis for statement {statement_id}: "
                f"{len(insights)} insights"
            )
    except Exception as e:
        logger.error(f"Post-upload analysis failed: {e}")
