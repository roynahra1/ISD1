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
        yield client

@patch('routes.appointment_routes.get_connection')
def test_search_appointments(mock_get_connection, client):
    """Test searching appointments with mocked database"""
    # Mock database response
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    
    response = client.get('/appointment/search?car_plate=TEST123')
    assert response.status_code == 200