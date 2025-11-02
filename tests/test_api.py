"""Tests for the API endpoints"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models import User, UserPreferences

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def client():
    """Create test client and database"""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)

def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "InternAlert" in response.json()["message"]

def test_register_user(client):
    """Test user registration"""
    user_data = {
        "email": "test@example.com",
        "preferences": {
            "job_types": ["Software Engineering"],
            "sponsorship_required": False,
            "locations": ["Remote"],
            "notification_frequency": "immediate"
        }
    }
    response = client.post("/api/users/register", json=user_data)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
    assert response.json()["id"] is not None

def test_register_duplicate_email(client):
    """Test duplicate email registration"""
    user_data = {
        "email": "duplicate@example.com",
        "preferences": {
            "job_types": ["Software Engineering"],
            "sponsorship_required": False,
            "locations": ["Remote"],
            "notification_frequency": "immediate"
        }
    }
    # First registration
    client.post("/api/users/register", json=user_data)
    # Second registration should fail
    response = client.post("/api/users/register", json=user_data)
    assert response.status_code == 400

def test_get_user(client):
    """Test getting user by email"""
    # First register a user
    user_data = {
        "email": "getuser@example.com",
        "preferences": {
            "job_types": ["Software Engineering"],
            "sponsorship_required": False,
            "locations": ["Remote"],
            "notification_frequency": "immediate"
        }
    }
    client.post("/api/users/register", json=user_data)
    
    # Then get the user
    response = client.get("/api/users/getuser@example.com")
    assert response.status_code == 200
    assert response.json()["email"] == "getuser@example.com"

def test_update_preferences(client):
    """Test updating user preferences"""
    # Register user first
    user_data = {
        "email": "update@example.com",
        "preferences": {
            "job_types": ["Software Engineering"],
            "sponsorship_required": False,
            "locations": ["Remote"],
            "notification_frequency": "immediate"
        }
    }
    client.post("/api/users/register", json=user_data)
    
    # Update preferences
    new_prefs = {
        "job_types": ["Data Science"],
        "sponsorship_required": True,
        "locations": ["San Francisco"],
        "notification_frequency": "daily_digest"
    }
    response = client.put("/api/users/update@example.com/preferences", json=new_prefs)
    assert response.status_code == 200

def test_unsubscribe_user(client):
    """Test unsubscribing a user"""
    # Register user first
    user_data = {
        "email": "unsub@example.com",
        "preferences": {
            "job_types": ["Software Engineering"],
            "sponsorship_required": False,
            "locations": ["Remote"],
            "notification_frequency": "immediate"
        }
    }
    client.post("/api/users/register", json=user_data)
    
    # Unsubscribe
    response = client.delete("/api/users/unsub@example.com")
    assert response.status_code == 200
    assert "unsubscribed" in response.json()["message"].lower()

def test_get_internships(client):
    """Test getting internships list"""
    response = client.get("/api/internships")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_internships_with_filters(client):
    """Test getting internships with filters"""
    response = client.get("/api/internships?position=Software&limit=10")
    assert response.status_code == 200

def test_get_stats(client):
    """Test getting system statistics"""
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert "total_users" in response.json()
    assert "total_internships" in response.json()

