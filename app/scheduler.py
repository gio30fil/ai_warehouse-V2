import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.sync_service import sync_softone_products, sync_softone_stock

logger = logging.getLogger(__name__)

_scheduler = None


def _run_sync_task():
    """Full sync: products + stock."""
    logger.info("Scheduled sync starting...")
    try:
        new_count = sync_softone_products()
        logger.info(f"Scheduled product sync: {new_count} new products.")

        updated_stock = sync_softone_stock()
        logger.info(f"Scheduled stock sync: {updated_stock} updates.")
    except Exception as e:
        logger.error(f"Scheduled sync error: {e}")


def start_scheduler():
    """Start APScheduler for daily sync at 8:00 AM."""
    global _scheduler

    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG"):
        return  # Avoid double scheduler in debug reloader

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_sync_task,
        "cron",
        hour=8,
        minute=0,
        id="daily_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started (daily sync at 08:00).")
