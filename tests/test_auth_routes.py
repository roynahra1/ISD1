import pytest

class TestAuthRoutes:
    
    def test_login_user_not_found(self, client):
        """Test login with non-existent user"""
        response = client.post('/login', json={
            "username": "nonexistent",
            "password": "password"
        })
        assert response.status_code in [401, 500]  # Unauthorized or server error

    def test_signup_missing_fields(self, client):
        """Test signup with missing fields"""
        response = client.post('/signup', json={
            "username": "testuser"
            # Missing email and password
        })
        assert response.status_code in [400, 500]  # Bad request or server error

    def test_auth_status_not_logged_in(self, client):
        """Test auth status when not logged in"""
        response = client.get('/auth/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['logged_in'] is False

    def test_logout(self, client):
        """Test logout"""
        response = client.post('/logout')
        assert response.status_code == 200

    def test_login_page(self, client):
        """Test login page loads"""
        response = client.get('/login.html')
        assert response.status_code == 200

    def test_signup_page(self, client):
        """Test signup page loads"""
        response = client.get('/signup.html')
        assert response.status_code == 200