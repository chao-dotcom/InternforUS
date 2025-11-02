"""Initialize the database by creating all tables"""
try:
    from app.database import engine, Base
    from app.models import User, UserPreferences, Internship, SentNotification, InternshipChange, Analytics
except ImportError:
    from database import engine, Base
    from models import User, UserPreferences, Internship, SentNotification, InternshipChange, Analytics

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()

