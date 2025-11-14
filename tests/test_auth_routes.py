import pytest
import json
from unittest.mock import patch
from werkzeug.security import generate_password_hash

class TestAuthRoutes:
    """Test authentication routes."""
    
    def test_login_page_accessible(self, client):
        """Test that login page is accessible."""
        response = client.get('/login.html')
        assert response.status_code == 200

    def test_signup_page_accessible(self, client):
        """Test that signup page is accessible."""
        response = client.get('/signup.html')
        assert response.status_code == 200

    def test_auth_status_unauthenticated(self, client):
        """Test auth status when not authenticated."""
        response = client.get('/auth/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['logged_in'] is False

    def test_logout(self, auth_client):
        """Test logout functionality."""
        response = auth_client.post('/logout')
        assert response.status_code == 200

    def test_auth_status_authenticated(self, auth_client):
        """Test auth status when authenticated."""
        response = auth_client.get('/auth/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['logged_in'] is True

    def test_signup_missing_fields(self, client):
        """Test signup with missing required fields."""
        test_cases = [
            {"username": "", "email": "test@test.com", "password": "pass123"},
            {"username": "test", "email": "", "password": "pass123"},
            {"username": "test", "email": "test@test.com", "password": ""},
        ]
        
        for data in test_cases:
            response = client.post('/signup', 
                                 data=json.dumps(data),
                                 content_type='application/json')
            assert response.status_code == 400

    def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        test_cases = [
            {"username": "", "password": "pass123"},
            {"username": "test", "password": ""},
        ]
        
        for data in test_cases:
            response = client.post('/login',
                                 data=json.dumps(data),
                                 content_type='application/json')
            assert response.status_code == 400