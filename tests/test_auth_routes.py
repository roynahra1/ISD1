import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            yield client

@patch('routes.auth_routes.get_connection')
def test_login_user_not_found(mock_get_connection, client):
    """Test login with non-existent user"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # User not found

    response = client.post('/login', json={
        "username": "nonexistent",
        "password": "password"
    })
    
    assert response.status_code == 401  # Unauthorized

@patch('routes.auth_routes.get_connection')
def test_signup_missing_fields(mock_get_connection, client):
    """Test signup with missing fields"""
    response = client.post('/signup', json={
        "username": "testuser"
        # Missing email and password
    })
    
    assert response.status_code == 400  # Bad request

def test_auth_status_not_logged_in(client):
    """Test auth status when not logged in"""
    response = client.get('/auth/status')
    assert response.status_code == 200
    data = response.get_json()
    assert data['logged_in'] is False

def test_logout(client):
    """Test logout"""
    response = client.post('/logout')
    assert response.status_code == 200

def test_login_page(client):
    """Test login page loads"""
    response = client.get('/login.html')
    assert response.status_code == 200

def test_signup_page(client):
    """Test signup page loads"""
    response = client.get('/signup.html')
    assert response.status_code == 200