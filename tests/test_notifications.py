"""Tests for the notification module"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User, UserPreferences, Internship, SentNotification
from app.notification import NotificationEngine
from datetime import datetime

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_notifications.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    """Create test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_user(db):
    """Create a sample user for testing"""
    user = User(email="test@example.com", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    prefs = UserPreferences(
        user_id=user.id,
        job_types=["Software Engineering"],
        sponsorship_required=False,
        locations=["Remote"],
        notification_frequency="immediate"
    )
    db.add(prefs)
    db.commit()
    return user

@pytest.fixture
def sample_internship(db):
    """Create a sample internship for testing"""
    internship = Internship(
        company_name="Test Company",
        position_title="Software Engineering Intern",
        locations=["Remote"],
        application_url="https://example.com/apply",
        sponsorship_info="Sponsorship available",
        date_scraped=datetime.utcnow(),
        is_active=True
    )
    db.add(internship)
    db.commit()
    db.refresh(internship)
    return internship

def test_notification_engine_init():
    """Test notification engine initialization"""
    engine = NotificationEngine()
    assert engine is not None
    assert engine.from_email is not None

def test_matches_preferences(db, sample_user, sample_internship):
    """Test preference matching logic"""
    engine = NotificationEngine()
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == sample_user.id).first()
    
    # Should match: Software Engineering in position, Remote in locations
    assert engine.matches_preferences(prefs, sample_internship) == True

def test_matches_preferences_job_type_filter(db, sample_user):
    """Test job type filtering"""
    engine = NotificationEngine()
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == sample_user.id).first()
    
    # Internship that doesn't match job type
    non_matching = Internship(
        company_name="Test",
        position_title="Marketing Intern",
        locations=["Remote"],
        application_url="https://example.com/apply2",
        sponsorship_info="Available"
    )
    
    assert engine.matches_preferences(prefs, non_matching) == False

def test_find_matching_users(db, sample_user, sample_internship):
    """Test finding users who match an internship"""
    engine = NotificationEngine()
    matching_users = engine.find_matching_users(db, sample_internship)
    
    assert len(matching_users) > 0
    assert sample_user in matching_users

def test_check_already_notified(db, sample_user, sample_internship):
    """Test checking if user was already notified"""
    engine = NotificationEngine()
    
    # Should not be notified yet
    assert engine.check_already_notified(db, sample_user.id, sample_internship.id) == False
    
    # Record notification
    engine.record_notification(db, sample_user.id, sample_internship.id)
    
    # Should be notified now
    assert engine.check_already_notified(db, sample_user.id, sample_internship.id) == True

def test_generate_email_html(db, sample_user, sample_internship):
    """Test email HTML generation"""
    engine = NotificationEngine()
    html = engine.generate_email_html(sample_user, [sample_internship])
    
    assert html is not None
    assert len(html) > 0
    assert "Test Company" in html
    assert sample_internship.application_url in html
    assert "internship" in html.lower()

def test_match_internships_to_users(db, sample_user, sample_internship):
    """Test matching internships to users"""
    engine = NotificationEngine()
    matches = engine.match_internships_to_users(db, [sample_internship])
    
    assert len(matches) > 0
    internship, users = matches[0]
    assert internship.id == sample_internship.id
    assert sample_user in users

