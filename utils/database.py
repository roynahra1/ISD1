import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

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