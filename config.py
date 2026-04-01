import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY                  = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI     = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS   = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {"sslmode": "require"},
    }
    APP_BASE_URL                = os.getenv("APP_BASE_URL", "http://localhost:5000")
    FYERS_REDIRECT_URI          = os.getenv("FYERS_REDIRECT_URI", "http://localhost:5000/fyers/callback")
    TIMEZONE                    = os.getenv("TIMEZONE", "Asia/Kolkata")
    WTF_CSRF_ENABLED            = True
    REMEMBER_COOKIE_DURATION    = 86400 * 7   # 7 days
