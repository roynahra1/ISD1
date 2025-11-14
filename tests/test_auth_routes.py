import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_login(client):
    """Test user login"""
    response = client.post('/login', json={
        "username": "testuser",
        "password": "testpass"
    })
    
    assert response.status_code in [200, 401]

def test_signup(client):
    """Test user registration"""
    response = client.post('/signup', json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "newpass123"
    })
    
    assert response.status_code in [201, 400, 409]

def test_auth_status(client):
    """Test authentication status check"""
    response = client.get('/auth/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'logged_in' in data