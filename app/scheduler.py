from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal
from .scraper import InternshipScraper
from .notification import NotificationEngine
from .models import Internship

def scrape_and_notify_job():
    """Job that runs daily to scrape and send notifications"""
    print(f"[{datetime.now()}] Starting scheduled scrape job...")
    
    db = SessionLocal()
    try:
        # Scrape internships
        scraper = InternshipScraper()
        scraped_data = scraper.scrape()
        
        print(f"Scraped {len(scraped_data)} internships")
        
        new_internships = []
        
        # Save to database
        for data in scraped_data:
            existing = db.query(Internship).filter(
                Internship.application_url == data['application_url']
            ).first()
            
            if not existing:
                internship = Internship(**data)
                db.add(internship)
                new_internships.append(internship)
        
        db.commit()
        
        print(f"Found {len(new_internships)} new internships")
        
        # Refresh to get IDs
        for internship in new_internships:
            db.refresh(internship)
        
        # Send notifications
        if new_internships:
            notifier = NotificationEngine()
            notifier.process_notifications(db, new_internships)
        
        print(f"[{datetime.now()}] Scrape job completed successfully")
        
    except Exception as e:
        print(f"Error in scrape job: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule job to run daily at 9:00 AM
    scheduler.add_job(
        scrape_and_notify_job,
        trigger=CronTrigger(hour=9, minute=0),
        id='daily_scrape',
        name='Daily internship scrape and notify',
        replace_existing=True
    )
    
    # For testing: run every 5 minutes (uncomment to use)
    # scheduler.add_job(
    #     scrape_and_notify_job,
    #     trigger='interval',
    #     minutes=5,
    #     id='test_scrape',
    #     name='Test scrape (every 5 min)'
    # )
    
    scheduler.start()
    print("Scheduler started! Job will run daily at 9:00 AM")
    
    return scheduler

# To integrate with FastAPI
def init_scheduler(app):
    """Initialize scheduler with FastAPI app"""
    scheduler = start_scheduler()
    
    @app.on_event("shutdown")
    def shutdown_scheduler():
        scheduler.shutdown()
        print("Scheduler shut down")
    
    return scheduler

if __name__ == "__main__":
    scheduler = start_scheduler()
    try:
        # Keep the script running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

