"""
config.py

Simple settings file. All values come from environment variables (.env)
so we never hardcode secrets or passwords in the code.
"""
import os
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    # MySQL database settings (used by PyMySQL, see app/db.py)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "hospital_db")

    # JWT settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "60"))
    JWT_REFRESH_TOKEN_EXPIRES_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # File uploads
    MAX_CONTENT_LENGTH = 512 * 1024  # 0.5 MB max file size
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

    # Cloudinary (used to store uploaded files)
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
