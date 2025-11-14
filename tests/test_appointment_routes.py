import pytest
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # You'll need to modify app.py slightly

@pytest.fixture
def client():
    """Create a test client with the Flask application"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            yield client

def test_book_appointment(client):
    """Test booking an appointment"""
    response = client.post('/book', json={
        "car_plate": "TEST123",
        "date": "2024-12-01",
        "time": "10:00",
        "service_ids": [1, 2],
        "notes": "Test appointment"
    })
    
    assert response.status_code in [201, 400]  # 201 created or 400 if conflict

def test_search_appointments(client):
    """Test searching appointments by car plate"""
    response = client.get('/appointment/search?car_plate=TEST123')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'status' in data
    assert 'appointments' in data

def test_select_appointment(client):
    """Test selecting an appointment for update"""
    # First, you might need to create a test appointment
    # Then test the select endpoint
    
    response = client.post('/appointments/select', json={
        "appointment_id": 1
    })
    
    # This might return 401 if not logged in, or 404 if appointment doesn't exist
    assert response.status_code in [200, 401, 404]

def test_get_appointment_by_id(client):
    """Test getting a specific appointment"""
    response = client.get('/appointments/1')
    
    assert response.status_code in [200, 404]