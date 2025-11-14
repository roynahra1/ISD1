import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

class TestUtils:
    """Test utility functions."""
    
    def test_serialize_datetime(self):
        """Test serializing datetime objects."""
        from utils.helpers import serialize
        
        now = datetime.now()
        result = serialize(now)
        assert isinstance(result, str)
    
    def test_serialize_timedelta(self):
        """Test serializing timedelta objects."""
        from utils.helpers import serialize
        
        delta = timedelta(days=1)
        result = serialize(delta)
        assert isinstance(result, str)
    
    def test_serialize_other_types(self):
        """Test serializing other data types."""
        from utils.helpers import serialize
        
        assert serialize("test") == "test"
        assert serialize(123) == 123
        assert serialize([1, 2, 3]) == [1, 2, 3]
        assert serialize({"key": "value"}) == {"key": "value"}
    
    def test_verify_password_success(self):
        """Test successful password verification."""
        from utils.helpers import verify_password
        from werkzeug.security import generate_password_hash
        
        password = "testpass123"
        hashed = generate_password_hash(password)
        
        result = verify_password(hashed, password)
        assert result is True
    
    def test_verify_password_failure(self):
        """Test failed password verification."""
        from utils.helpers import verify_password
        from werkzeug.security import generate_password_hash
        
        password = "testpass123"
        wrong_password = "wrongpass"
        hashed = generate_password_hash(password)
        
        result = verify_password(hashed, wrong_password)
        assert result is False
    
    def test_verify_password_none_hash(self):
        """Test password verification with None hash."""
        from utils.helpers import verify_password
        
        result = verify_password(None, "password")
        assert result is False
    
    def test_database_connection(self):
        """Test database connection utility."""
        with patch('mysql.connector.connect') as mock_connect:
            from utils.database import get_connection
            get_connection()
            mock_connect.assert_called_once()
    
    def test_safe_close(self):
        """Test safe_close utility."""
        from utils.database import _safe_close
        
        # Should not raise exceptions with None values
        _safe_close()
        _safe_close(None, None)