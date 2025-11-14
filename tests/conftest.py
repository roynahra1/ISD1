import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def app():
    """Create test Flask app."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """Authenticated test client."""
    with client.session_transaction() as session:
        session['logged_in'] = True
        session['username'] = 'testuser'
        session['selected_appointment_id'] = 1
        session['selected_appointment'] = {
            'Appointment_id': 1,
            'Date': '2024-01-15',
            'Time': '10:00',
            'Car_plate': 'TEST123'
        }
    return client

@pytest.fixture
def mock_db():
    """Mock database connection."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.start_transaction = Mock()
    mock_conn.commit = Mock()
    mock_conn.rollback = Mock()
    
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.lastrowid = 1
    
    with patch('routes.auth_routes.get_connection', return_value=mock_conn), \
         patch('routes.appointment_routes.get_connection', return_value=mock_conn):
        yield mock_conn, mock_cursor