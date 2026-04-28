import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.sync_service import sync_softone_products, sync_softone_stock

logger = logging.getLogger(__name__)

_scheduler = None


def _run_incremental_sync():
    """Incremental sync: fetches products updated in the last 30 days + stock."""
    logger.info("Incremental sync starting...")
    try:
        # Use 30-day lookback for incremental updates
        lookback_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        new_count = sync_softone_products(upddate_from=lookback_date)
        logger.info(f"Incremental product sync: {new_count} new products.")

        updated_stock = sync_softone_stock()
        logger.info(f"Incremental stock sync: {updated_stock} updates.")
    except Exception as e:
        logger.error(f"Incremental sync error: {e}")


def _run_full_sync():
    """Full sync: fetches ALL products from SoftOne (since 2020)."""
    logger.info("Full daily sync starting...")
    try:
        new_count = sync_softone_products(upddate_from="2020-01-01T00:00:00")
        logger.info(f"Full product sync: {new_count} new products.")

        updated_stock = sync_softone_stock()
        logger.info(f"Full stock sync: {updated_stock} updates.")
    except Exception as e:
        logger.error(f"Full sync error: {e}")


def start_scheduler():
    """Start APScheduler for periodic sync every 5 minutes + daily full sync."""
    global _scheduler

    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG"):
        return  # Avoid double scheduler in debug reloader

    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()

    # Incremental sync every 5 minutes (last 30 days only — fast)
    _scheduler.add_job(
        _run_incremental_sync,
        "interval",
        minutes=5,
        id="incremental_sync",
        replace_existing=True,
    )

    # Full sync once per day at 03:00 AM (catches ALL products)
    _scheduler.add_job(
        _run_full_sync,
        "cron",
        hour=3,
        minute=0,
        id="daily_full_sync",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Background scheduler started (incremental every 5min + daily full sync at 03:00).")
