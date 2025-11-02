from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./internships.db"
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "alerts@internalert.com"
    SECRET_KEY: str = ""  # Must be set via .env file in production
    
    class Config:
        env_file = ".env"

settings = Settings()

