"""
config.py

Simple settings file. All values come from environment variables (.env)
so we never hardcode secrets or passwords in the code.
"""
import os
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()


def _parse_database_url(url: str):
    """
    Parses a single database connection string (e.g. Aiven's "Service URI",
    or Railway/Render's DATABASE_URL) into the individual pieces PyMySQL
    needs. Handles URLs like:
        mysql://user:password@host:port/dbname?ssl-mode=REQUIRED
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    ssl_required = query.get("ssl-mode", [""])[0].upper() == "REQUIRED" or "ssl" in query
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "name": parsed.path.lstrip("/"),
        "ssl": ssl_required,
    }


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    # MySQL database settings (used by PyMySQL, see app/db.py)
    #
    # Two ways to configure the database — use whichever is easier:
    #   1. Set DATABASE_URL to a single connection string, e.g. Aiven's
    #      "Service URI": mysql://user:pass@host:port/dbname?ssl-mode=REQUIRED
    #   2. Or set DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / DB_SSL
    #      individually (used if DATABASE_URL isn't set).
    _database_url = os.getenv("DATABASE_URL")
    if _database_url:
        _parsed = _parse_database_url(_database_url)
        DB_HOST = _parsed["host"]
        DB_PORT = _parsed["port"]
        DB_USER = _parsed["user"]
        DB_PASSWORD = _parsed["password"]
        DB_NAME = _parsed["name"]
        DB_SSL = _parsed["ssl"]
    else:
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = int(os.getenv("DB_PORT", "3306"))
        DB_SSL = os.getenv("DB_SSL", "false").lower() == "true"
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
