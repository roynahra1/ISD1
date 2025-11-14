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

@patch('routes.appointment_routes.get_connection')
def test_book_appointment(mock_get_connection, client):
    """Test booking an appointment with mocked database"""
    # Mock database response
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.start_transaction.return_value = None
    mock_cursor.fetchone.side_effect = [None, None]  # No time conflict, no car exists
    mock_cursor.fetchall.return_value = [(1,), (2,), (3,), (4,)]  # Valid service IDs
    mock_cursor.lastrowid = 123

    response = client.post('/book', json={
        "car_plate": "TEST123",
        "date": "2024-12-01",
        "time": "10:00",
        "service_ids": [1, 2],
        "notes": "Test appointment"
    })
    
    # Should return 400 (bad request) due to validation, not 500
    assert response.status_code == 400

@patch('routes.appointment_routes.get_connection')
def test_search_appointments(mock_get_connection, client):
    """Test searching appointments with mocked database"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []  # Empty result

    response = client.get('/appointment/search?car_plate=TEST123')
    assert response.status_code == 200
    data = response.get_json()
    assert 'status' in data
    assert 'appointments' in data

@patch('routes.appointment_routes.get_connection')
def test_get_appointment_by_id(mock_get_connection, client):
    """Test getting a specific appointment with mocked database"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None  # Appointment not found

    response = client.get('/appointments/999')  # Non-existent ID
    assert response.status_code == 404

def test_select_appointment_without_login(client):
    """Test selecting appointment without login"""
    response = client.post('/appointments/select', json={
        "appointment_id": 1
    })
    assert response.status_code == 401  # Unauthorized

def test_get_current_appointment_without_login(client):
    """Test getting current appointment without login"""
    response = client.get('/appointments/current')
    assert response.status_code == 401  # Unauthorized

def test_update_appointment_without_login(client):
    """Test updating appointment without login"""
    response = client.put('/appointments/update', json={})
    assert response.status_code == 401  # Unauthorized

def test_delete_appointment_without_login(client):
    """Test deleting appointment without login"""
    response = client.delete('/appointments/1')
    assert response.status_code == 401  # Unauthorized