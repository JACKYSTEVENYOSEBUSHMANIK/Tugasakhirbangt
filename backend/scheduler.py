# backend/scheduler.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()

def daily_pruning_job():
    logger.info("Running scheduled data pruning job...")
    try:
        cfg = database.get_pruning_config()
        retention_days = cfg.get("retention_days", 30)
        success = database.execute_pruning(retention_days)
        if success:
            logger.info(f"Data pruning completed successfully (retention: {retention_days} days)")
            database.save_system_log("INFO", "SYSTEM", f"Pembersihan database otomatis berhasil dijalankan. Data > {retention_days} hari dibersihkan.")
        else:
            logger.error("Data pruning job failed")
            database.save_system_log("ERROR", "SYSTEM", "Pembersihan database otomatis gagal dijalankan.")
    except Exception as e:
        logger.error(f"Error in data pruning job: {e}")
        database.save_system_log("ERROR", "SYSTEM", f"Kesalahan pada job pembersihan database: {str(e)}")

def start_scheduler():
    if not scheduler.running:
        # Run pruning once daily (every 24 hours)
        scheduler.add_job(daily_pruning_job, "interval", hours=24, id="daily_pruning")
        scheduler.start()
        logger.info("Background scheduler started successfully")
        database.save_system_log("INFO", "SYSTEM", "Scheduler latar belakang berhasil dijalankan.")
