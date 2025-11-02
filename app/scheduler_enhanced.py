from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal
from .scraper_enhanced import EnhancedInternshipScraper
from .notification_enhanced import EnhancedNotificationEngine

def scrape_job():
    """Daily scraping job with change detection"""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] Starting scheduled scrape job")
    print(f"{'='*50}")
    
    db = SessionLocal()
    try:
        scraper = EnhancedInternshipScraper()
        new_internships, updated_internships = scraper.scrape_and_process(db)
        
        # Send immediate notifications
        notifier = EnhancedNotificationEngine()
        notifier.process_immediate_notifications(db, new_internships, updated_internships)
        
        print(f"\n✓ Scrape job completed successfully")
        print(f"  - New: {len(new_internships)}")
        print(f"  - Updated: {len(updated_internships)}")
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"❌ Error in scrape job: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

def daily_digest_job():
    """Send daily digest emails"""
    print(f"[{datetime.now()}] Processing daily digests...")
    
    db = SessionLocal()
    try:
        notifier = EnhancedNotificationEngine()
        notifier.process_daily_digests(db)
        print("✓ Daily digests sent")
    except Exception as e:
        print(f"❌ Error in daily digest job: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def weekly_digest_job():
    """Send weekly digest emails"""
    print(f"[{datetime.now()}] Processing weekly digests...")
    
    db = SessionLocal()
    try:
        notifier = EnhancedNotificationEngine()
        notifier.process_weekly_digests(db)
        print("✓ Weekly digests sent")
    except Exception as e:
        print(f"❌ Error in weekly digest job: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def start_scheduler():
    """Initialize all scheduled jobs"""
    scheduler = BackgroundScheduler()
    
    # Daily scrape at 9:00 AM
    scheduler.add_job(
        scrape_job,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_scrape',
        name='Daily internship scrape',
        replace_existing=True
    )
    
    # Check for daily digests every hour
    scheduler.add_job(
        daily_digest_job,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id='daily_digest_check',
        name='Daily digest sender',
        replace_existing=True
    )
    
    # Check for weekly digests every hour
    scheduler.add_job(
        weekly_digest_job,
        trigger=CronTrigger(minute=0),
        id='weekly_digest_check',
        name='Weekly digest sender',
        replace_existing=True
    )
    
    # FOR TESTING: Uncomment to run scrape every 5 minutes
    # scheduler.add_job(
    #     scrape_job,
    #     trigger='interval',
    #     minutes=5,
    #     id='test_scrape',
    #     name='Test scrape (every 5 min)'
    # )
    
    scheduler.start()
    print("✓ Scheduler started!")
    print("  - Daily scrape: 9:00 AM")
    print("  - Digest checks: Every hour")
    
    return scheduler

def init_scheduler(app):
    """Initialize scheduler with FastAPI"""
    scheduler = start_scheduler()
    
    @app.on_event("shutdown")
    def shutdown_scheduler():
        scheduler.shutdown()
        print("Scheduler shut down")
    
    return scheduler

