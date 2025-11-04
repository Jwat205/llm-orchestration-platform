# security-service/app/config.py
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Security service configuration"""
    
    # Basic settings
    DEBUG: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Security
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.yourdomain.com"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://yourdomain.com"]
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Encryption
    MASTER_ENCRYPTION_KEY: str = os.getenv("MASTER_ENCRYPTION_KEY", "")
    KEY_ROTATION_INTERVAL_DAYS: int = 90
    
    # External Services
    DJANGO_SERVICE_URL: str = os.getenv("DJANGO_SERVICE_URL", "http://localhost:8000")
    FASTAPI_SERVICE_URL: str = os.getenv("FASTAPI_SERVICE_URL", "http://localhost:8002")
    
    # Monitoring
    ENABLE_MONITORING: bool = True
    SCAN_INTERVAL_MINUTES: int = 15
    THREAT_DETECTION_ENABLED: bool = True
    ANOMALY_DETECTION_ENABLED: bool = True
    
    # Compliance
    SOC2_ENABLED: bool = True
    GDPR_ENABLED: bool = True
    HIPAA_ENABLED: bool = False
    PCI_DSS_ENABLED: bool = False
    
    # Alerting
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    EMAIL_SMTP_HOST: str = os.getenv("EMAIL_SMTP_HOST", "")
    EMAIL_SMTP_PORT: int = 587
    EMAIL_USERNAME: str = os.getenv("EMAIL_USERNAME", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = True

def get_settings() -> Settings:
    """Get application settings"""
    return Settings()