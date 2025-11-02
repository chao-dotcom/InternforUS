from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

from .database import get_db, engine, Base
from .models import User, UserPreferences, Internship, InternshipChange
from .scraper import InternshipScraper
from .scraper_enhanced import EnhancedInternshipScraper
from .notification import NotificationEngine
from .notification_enhanced import EnhancedNotificationEngine
from .scheduler_enhanced import init_scheduler
from .analytics import router as analytics_router

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Intern For US API",
    version="2.0.0",
    description="Automated internship notification system with change detection and digests"
)

# Include analytics router
app.include_router(analytics_router)

# Initialize enhanced scheduler
init_scheduler(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🚀 Intern For US API Started!")
    print("="*50)
    print("Features:")
    print("  ✓ Smart change detection")
    print("  ✓ Daily/weekly email digests")
    print("  ✓ Analytics tracking")
    print("  ✓ Custom user filters")
    print("\nScheduler:")
    print("  ✓ Daily scrape at 9:00 AM")
    print("  ✓ Digest emails sent hourly")
    print("="*50 + "\n")

@app.get("/dashboard.html")
async def serve_dashboard():
    """Serve the dashboard HTML file"""
    from fastapi.responses import FileResponse
    import os
    dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    else:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Dashboard not found"}, status_code=404)

# Pydantic models for requests/responses
class UserPreferencesSchema(BaseModel):
    job_types: List[str]
    sponsorship_required: bool
    locations: List[str]
    notification_frequency: str = "immediate"
    digest_time: Optional[str] = "09:00"  # HH:MM format
    digest_day: Optional[str] = "monday"  # For weekly digests

class UserRegistration(BaseModel):
    email: EmailStr
    preferences: UserPreferencesSchema

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class InternshipResponse(BaseModel):
    id: int
    company_name: str
    position_title: str
    locations: List[str]
    application_url: str
    sponsorship_info: str
    date_scraped: Optional[datetime] = None
    date_first_seen: Optional[datetime] = None
    date_last_updated: Optional[datetime] = None
    change_count: int = 0
    
    class Config:
        from_attributes = True

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Intern For US API",
        "version": "2.0.0",
        "features": [
            "Smart change detection",
            "Daily/weekly digests",
            "Analytics dashboard",
            "Custom filters"
        ],
        "docs": "/docs"
    }

@app.post("/api/users/register", response_model=UserResponse)
async def register_user(user_data: UserRegistration, db: Session = Depends(get_db)):
    """Register new user with preferences"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate notification frequency
    valid_frequencies = ["immediate", "daily", "weekly"]
    if user_data.preferences.notification_frequency not in valid_frequencies:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid frequency. Must be one of: {valid_frequencies}"
        )
    
    # Create user
    user = User(email=user_data.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user.id,
        job_types=user_data.preferences.job_types,
        sponsorship_required=user_data.preferences.sponsorship_required,
        locations=user_data.preferences.locations,
        notification_frequency=user_data.preferences.notification_frequency,
        digest_time=user_data.preferences.digest_time,
        digest_day=user_data.preferences.digest_day.lower()
    )
    db.add(preferences)
    db.commit()
    
    return user

@app.get("/api/users/{email}", response_model=UserResponse)
async def get_user(email: str, db: Session = Depends(get_db)):
    """Get user by email"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/users/{email}/preferences")
async def get_user_preferences(email: str, db: Session = Depends(get_db)):
    """Get user preferences"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.preferences:
        raise HTTPException(status_code=404, detail="Preferences not found")
    
    return {
        "job_types": user.preferences.job_types,
        "sponsorship_required": user.preferences.sponsorship_required,
        "locations": user.preferences.locations,
        "notification_frequency": user.preferences.notification_frequency,
        "digest_time": user.preferences.digest_time,
        "digest_day": user.preferences.digest_day
    }

@app.put("/api/users/{email}/preferences")
async def update_preferences(
    email: str,
    preferences: UserPreferencesSchema,
    db: Session = Depends(get_db)
):
    """Update user preferences"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_prefs = user.preferences
    if not user_prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")
    
    # Update all fields
    user_prefs.job_types = preferences.job_types
    user_prefs.sponsorship_required = preferences.sponsorship_required
    user_prefs.locations = preferences.locations
    user_prefs.notification_frequency = preferences.notification_frequency
    user_prefs.digest_time = preferences.digest_time
    user_prefs.digest_day = preferences.digest_day.lower()
    
    db.commit()
    
    return {"message": "Preferences updated successfully"}

@app.delete("/api/users/{email}")
async def unsubscribe_user(email: str, db: Session = Depends(get_db)):
    """Unsubscribe user"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    
    return {"message": "Successfully unsubscribed"}

@app.get("/api/internships", response_model=List[InternshipResponse])
async def get_internships(
    company: Optional[str] = None,
    position: Optional[str] = None,
    location: Optional[str] = None,
    sponsorship: Optional[str] = None,
    updated_recently: bool = False,
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get internships with optional filters (max 100) - shows all matching internships from database"""
    from sqlalchemy import or_, func
    
    query = db.query(Internship).filter(Internship.is_active == True)
    
    if company:
        query = query.filter(Internship.company_name.ilike(f"%{company}%"))
    if position:
        query = query.filter(Internship.position_title.ilike(f"%{position}%"))
    if sponsorship:
        query = query.filter(Internship.sponsorship_info.ilike(f"%{sponsorship}%"))
    if location:
        # Handle JSON array locations field - check if location appears in any of the location strings
        # For SQLite, we'll use a simple text cast approach
        from sqlalchemy import String, or_
        # Cast JSON to string and search (works for SQLite)
        # This will search within the JSON string representation
        query = query.filter(
            func.cast(Internship.locations, String).ilike(f"%{location}%")
        )
    if updated_recently:
        query = query.filter(Internship.change_count > 0)
    
    internships = query.order_by(Internship.date_last_updated.desc()).limit(limit).all()
    
    return internships

@app.get("/api/internships/{internship_id}", response_model=InternshipResponse)
async def get_internship(internship_id: int, db: Session = Depends(get_db)):
    """Get specific internship with change history"""
    internship = db.query(Internship).filter(Internship.id == internship_id).first()
    if not internship:
        raise HTTPException(status_code=404, detail="Internship not found")
    return internship

@app.get("/api/internships/latest", response_model=List[InternshipResponse])
async def get_latest_internships(
    hours: int = 24,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get new internships since last check (default: last 24 hours)"""
    from datetime import datetime, timedelta
    
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    internships = db.query(Internship).filter(
        Internship.is_active == True,
        Internship.date_first_seen >= cutoff_time
    ).order_by(Internship.date_first_seen.desc()).limit(limit).all()
    
    return internships

@app.post("/api/scrape")
async def trigger_scrape(
    section: str = None,
    db: Session = Depends(get_db)
):
    """Manually trigger a scrape (for testing)
    
    Args:
        section: Optional section name to filter (e.g., "Software Engineering")
                Only internships from that section will be scraped.
                Valid sections: "Software Engineering", "Product Management", 
                "Data Science", "Quantitative Finance", "Hardware Engineering", etc.
    """
    try:
        scraper = EnhancedInternshipScraper()
        
        # First, test if we can fetch the markdown
        markdown = scraper.fetch_markdown()
        if not markdown:
            return {
                "message": "Scrape failed",
                "error": "Could not fetch markdown from GitHub. Check your internet connection and GitHub URL.",
                "new_internships": 0,
                "updated_internships": 0,
                "total_internships_in_db": db.query(Internship).filter(Internship.is_active == True).count()
            }
        
        # Test parsing with section filter if provided
        test_parsed = scraper.parse_markdown_table(markdown, section_filter=section)
        if len(test_parsed) == 0:
            # Debug: Check what we got - search the ENTIRE file, not just first 100 lines
            lines = markdown.split('\n')
            all_pipes = [i for i, line in enumerate(lines) if '|' in line]
            company_lines = [i for i, line in enumerate(lines) if '|' in line and ('Company' in line or 'company' in line.lower())]
            sample_table_line = next((f"Line {i}: {line[:150]}" for i, line in enumerate(lines) if '|' in line and 'Company' in line), "No table header found")
            
            return {
                "message": "Scrape completed but found 0 internships",
                "error": "Parser found no internships. The GitHub markdown format may have changed or table is empty.",
                "section_filter": section,
                "debug_info": {
                    "markdown_length": len(markdown),
                    "total_lines": len(lines),
                    "github_url": scraper.github_url,
                    "has_table_lines": len(all_pipes) > 0,
                    "table_lines_count": len(all_pipes),
                    "found_company_header": len(company_lines) > 0,
                    "company_header_line_numbers": company_lines[:5] if company_lines else [],
                    "sample_table_line": sample_table_line,
                    "first_500_chars": markdown[:500] if len(markdown) > 0 else "Empty markdown",
                    "note": "Tables are usually further down in the file, not at the beginning"
                },
                "new_internships": 0,
                "updated_internships": 0,
                "total_internships_in_db": db.query(Internship).filter(Internship.is_active == True).count(),
                "troubleshooting": "Check if the GitHub URL is correct and the markdown table format matches expected structure"
            }
        
        new_internships, updated_internships = scraper.scrape_and_process(db, section_filter=section)
        
        # Get total internships in database for context
        total_in_db = db.query(Internship).filter(Internship.is_active == True).count()
        
        # Send immediate notifications
        notifier = EnhancedNotificationEngine()
        notifier.process_immediate_notifications(db, new_internships, updated_internships)
        
        return {
            "message": f"Scrape completed successfully{' (section: ' + section + ')' if section else ''}",
            "section_filter": section,
            "new_internships": len(new_internships),
            "updated_internships": len(updated_internships),
            "total_internships_in_db": total_in_db,
            "note": "If new_internships is 0, internships may already be in the database. Check /api/internships to see all internships."
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Scrape error: {error_details}")
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")

@app.get("/api/internships/{internship_id}/changes")
async def get_internship_changes(internship_id: int, db: Session = Depends(get_db)):
    """Get change history for an internship"""
    changes = db.query(InternshipChange).filter(
        InternshipChange.internship_id == internship_id
    ).order_by(InternshipChange.detected_at.desc()).all()
    
    return [
        {
            "change_type": c.change_type,
            "changed_fields": c.changed_fields,
            "old_values": c.old_values,
            "new_values": c.new_values,
            "detected_at": c.detected_at
        }
        for c in changes
    ]

@app.get("/api/stats")
async def get_basic_stats(db: Session = Depends(get_db)):
    """Get basic system statistics"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_internships = db.query(Internship).count()
    active_internships = db.query(Internship).filter(Internship.is_active == True).count()
    
    # Notification frequency breakdown
    immediate = db.query(User).join(UserPreferences).filter(
        UserPreferences.notification_frequency == "immediate"
    ).count()
    daily = db.query(User).join(UserPreferences).filter(
        UserPreferences.notification_frequency == "daily"
    ).count()
    weekly = db.query(User).join(UserPreferences).filter(
        UserPreferences.notification_frequency == "weekly"
    ).count()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "by_frequency": {
                "immediate": immediate,
                "daily": daily,
                "weekly": weekly
            }
        },
        "internships": {
            "total": total_internships,
            "active": active_internships
        }
    }

