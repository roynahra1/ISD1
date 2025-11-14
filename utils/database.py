import os
import mysql.connector
from mysql.connector import Error

def get_db_config():
    """Get database configuration with test environment support"""
    if os.getenv('TESTING'):
        # Use test database for tests
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("TEST_DB_NAME", "isd_test"),  # Different DB for tests
            "auth_plugin": "mysql_native_password"
        }
    else:
        # Use production database
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "isd"),
            "auth_plugin": "mysql_native_password"
        }

def get_connection():
    """Get database connection with error handling"""
    try:
        return mysql.connector.connect(**get_db_config())
    except Error as e:
        print(f"Database connection error: {e}")
        raise

def _safe_close(cursor=None, conn=None):
    try:
        if cursor:
            cursor.close()
    except Exception:
        pass
    try:
        if conn:
            conn.close()
    except Exception:
        pass