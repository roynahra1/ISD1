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