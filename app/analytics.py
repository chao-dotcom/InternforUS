from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Dict
from .database import get_db
from .models import Analytics, Internship, User, SentNotification, InternshipChange

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/dashboard")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get overall system statistics"""
    
    # Current stats
    total_internships = db.query(Internship).filter(Internship.is_active == True).count()
    total_users = db.query(User).filter(User.is_active == True).count()
    
    # Last 7 days
    last_week = datetime.utcnow() - timedelta(days=7)
    new_this_week = db.query(Internship).filter(
        Internship.date_first_seen >= last_week
    ).count()
    
    updated_this_week = db.query(Internship).filter(
        and_(
            Internship.date_last_updated >= last_week,
            Internship.date_first_seen < last_week
        )
    ).count()
    
    # Today's activity
    today = datetime.utcnow().date()
    today_analytics = db.query(Analytics).filter(
        Analytics.date >= datetime.combine(today, datetime.min.time())
    ).first()
    
    emails_sent_today = today_analytics.emails_sent if today_analytics else 0
    
    return {
        "overview": {
            "total_active_internships": total_internships,
            "total_active_users": total_users,
            "new_this_week": new_this_week,
            "updated_this_week": updated_this_week,
            "emails_sent_today": emails_sent_today
        },
        "last_scrape": today_analytics.date if today_analytics else None,
        "scrape_success": today_analytics.scrape_success if today_analytics else None
    }

@router.get("/trending/companies")
async def get_trending_companies(limit: int = 10, db: Session = Depends(get_db)):
    """Get companies with most internship postings"""
    
    result = db.query(
        Internship.company_name,
        func.count(Internship.id).label('count')
    ).filter(
        Internship.is_active == True
    ).group_by(
        Internship.company_name
    ).order_by(
        func.count(Internship.id).desc()
    ).limit(limit).all()
    
    return [
        {"company": row[0], "count": row[1]}
        for row in result
    ]

@router.get("/trending/roles")
async def get_trending_roles(limit: int = 10, db: Session = Depends(get_db)):
    """Get most common role types"""
    
    # Extract role keywords from position titles
    result = db.query(
        Internship.position_title,
        func.count(Internship.id).label('count')
    ).filter(
        Internship.is_active == True
    ).group_by(
        Internship.position_title
    ).order_by(
        func.count(Internship.id).desc()
    ).limit(limit).all()
    
    return [
        {"role": row[0], "count": row[1]}
        for row in result
    ]

@router.get("/history")
async def get_history(days: int = 30, db: Session = Depends(get_db)):
    """Get historical analytics data"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    analytics = db.query(Analytics).filter(
        Analytics.date >= start_date
    ).order_by(Analytics.date.desc()).all()
    
    return [
        {
            "date": a.date.isoformat(),
            "internships_added": a.internships_added,
            "internships_updated": a.internships_updated,
            "internships_removed": a.internships_removed,
            "emails_sent": a.emails_sent,
            "scrape_duration": a.scrape_duration_seconds,
            "success": a.scrape_success
        }
        for a in analytics
    ]

@router.get("/weekly-summary")
async def get_weekly_summary(db: Session = Depends(get_db)):
    """Get summary of last 7 days"""
    
    last_week = datetime.utcnow() - timedelta(days=7)
    
    # Aggregate data
    total_added = db.query(func.sum(Analytics.internships_added)).filter(
        Analytics.date >= last_week
    ).scalar() or 0
    
    total_updated = db.query(func.sum(Analytics.internships_updated)).filter(
        Analytics.date >= last_week
    ).scalar() or 0
    
    total_emails = db.query(func.sum(Analytics.emails_sent)).filter(
        Analytics.date >= last_week
    ).scalar() or 0
    
    # Most active day
    most_active = db.query(Analytics).filter(
        Analytics.date >= last_week
    ).order_by(Analytics.internships_added.desc()).first()
    
    return {
        "period": "Last 7 days",
        "total_internships_added": total_added,
        "total_internships_updated": total_updated,
        "total_emails_sent": total_emails,
        "most_active_day": most_active.date.isoformat() if most_active else None,
        "most_active_count": most_active.internships_added if most_active else 0
    }

@router.get("/user-engagement")
async def get_user_engagement(db: Session = Depends(get_db)):
    """Get user engagement metrics"""
    
    # Notification frequency breakdown
    from .models import UserPreferences
    freq_breakdown = db.query(
        UserPreferences.notification_frequency,
        func.count(User.id)
    ).join(UserPreferences, UserPreferences.user_id == User.id).filter(
        User.is_active == True
    ).group_by(UserPreferences.notification_frequency).all()
    
    # Recent signups
    last_month = datetime.utcnow() - timedelta(days=30)
    recent_signups = db.query(User).filter(
        User.created_at >= last_month
    ).count()
    
    return {
        "notification_preferences": {
            row[0]: row[1] for row in freq_breakdown
        },
        "signups_last_30_days": recent_signups
    }

