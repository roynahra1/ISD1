import pytest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from utils.helpers import serialize, verify_password

class TestUtils:
    
    def test_serialize_datetime(self):
        """Test serializing datetime objects"""
        test_date = datetime(2024, 1, 1, 10, 30, 0)
        result = serialize(test_date)
        assert isinstance(result, str)
    
    def test_serialize_timedelta(self):
        """Test serializing timedelta objects"""
        test_delta = timedelta(hours=2, minutes=30)
        result = serialize(test_delta)
        assert isinstance(result, str)
    
    def test_serialize_regular_value(self):
        """Test serializing regular values"""
        result = serialize("test string")
        assert result == "test string"
        
        result = serialize(123)
        assert result == 123
    
    def test_verify_password_success(self):
        """Test successful password verification"""
        password = "testpassword123"
        hashed = generate_password_hash(password)
        result = verify_password(hashed, password)
        assert result is True
    
    def test_verify_password_failure(self):
        """Test failed password verification"""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = generate_password_hash(password)
        result = verify_password(hashed, wrong_password)
        assert result is False
    
    def test_verify_password_none_hash(self):
        """Test password verification with None hash"""
        result = verify_password(None, "anypassword")
        assert result is False