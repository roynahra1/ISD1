from datetime import datetime, timedelta
from typing import Any
from werkzeug.security import check_password_hash

def serialize(val: Any) -> Any:
    if isinstance(val, (datetime, timedelta)):
        return str(val)
    return val

def verify_password(stored_hash: str, supplied_password: str) -> bool:
    """Verify password using Werkzeug's check_password_hash"""
    if not stored_hash:
        return False
    try:
        return check_password_hash(stored_hash, supplied_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False