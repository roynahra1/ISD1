import os

# Secret Key
SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-in-production")

# Session Configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "isd"),
    "auth_plugin": "mysql_native_password"
}

# Flask Configuration
DEBUG = True
TESTING = False