from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
    notifications = relationship("SentNotification", back_populates="user")

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Filter preferences
    job_types = Column(JSON)  # ["Software Engineering", "Data Science"]
    sponsorship_required = Column(Boolean, default=False)
    locations = Column(JSON)  # ["Remote", "New York", "San Francisco"]
    
    # Notification preferences
    notification_frequency = Column(String, default="immediate")  # immediate, daily, weekly
    digest_time = Column(String, default="09:00")  # Time to send digest (HH:MM)
    digest_day = Column(String, default="monday")  # For weekly digests
    
    user = relationship("User", back_populates="preferences")

class Internship(Base):
    __tablename__ = "internships"
    
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False, index=True)
    position_title = Column(String, nullable=False)
    locations = Column(JSON)
    application_url = Column(String, unique=True, nullable=False)
    sponsorship_info = Column(Text)
    
    # Change tracking
    date_posted = Column(DateTime)
    date_first_seen = Column(DateTime, default=datetime.utcnow)
    date_last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Track changes
    previous_data = Column(JSON)  # Store previous version for comparison
    change_count = Column(Integer, default=0)
    
    notifications = relationship("SentNotification", back_populates="internship")
    changes = relationship("InternshipChange", back_populates="internship")

class SentNotification(Base):
    __tablename__ = "sent_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    internship_id = Column(Integer, ForeignKey("internships.id"))
    sent_at = Column(DateTime, default=datetime.utcnow)
    notification_type = Column(String)  # "new", "update", "digest", "immediate"
    
    user = relationship("User", back_populates="notifications")
    internship = relationship("Internship", back_populates="notifications")

# Track internship changes
class InternshipChange(Base):
    __tablename__ = "internship_changes"
    
    id = Column(Integer, primary_key=True, index=True)
    internship_id = Column(Integer, ForeignKey("internships.id"))
    change_type = Column(String)  # "created", "updated", "location_changed", etc.
    changed_fields = Column(JSON)
    old_values = Column(JSON)
    new_values = Column(JSON)
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    internship = relationship("Internship", back_populates="changes")

# Analytics tracking
class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Daily metrics
    internships_added = Column(Integer, default=0)
    internships_updated = Column(Integer, default=0)
    internships_removed = Column(Integer, default=0)
    
    # Popular companies/roles
    top_companies = Column(JSON)  # [{"company": "Google", "count": 5}, ...]
    top_roles = Column(JSON)
    
    # User metrics
    active_users = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    
    # Scraping metrics
    scrape_duration_seconds = Column(Float)
    scrape_success = Column(Boolean, default=True)
    scrape_error = Column(Text)

