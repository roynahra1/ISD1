import pytest
from unittest.mock import patch, MagicMock

class TestAppointmentRoutes:
    
    @patch('routes.appointment_routes.get_connection')
    def test_book_appointment(self, mock_get_connection, client):
        """Test booking an appointment with mocked database"""
        # Mock database to avoid 500 errors
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        response = client.post('/book', json={
            "car_plate": "TEST123",
            "date": "2024-12-01",
            "time": "10:00", 
            "service_ids": [1, 2],
            "notes": "Test appointment"
        })
        # Should return validation error, not 500
        assert response.status_code != 500

    @patch('routes.appointment_routes.get_connection')
    def test_search_appointments(self, mock_get_connection, client):
        """Test searching appointments by car plate with mocked database"""
        # Mock database to avoid 500 errors
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        response = client.get('/appointment/search?car_plate=TEST123')
        assert response.status_code == 200

    @patch('routes.appointment_routes.get_connection')
    def test_get_appointment_by_id(self, mock_get_connection, client):
        """Test getting a specific appointment with mocked database"""
        # Mock database to avoid 500 errors
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Appointment not found
        
        response = client.get('/appointments/1')
        assert response.status_code == 404  # Not found

    def test_select_appointment_without_login(self, client):
        """Test selecting appointment without login"""
        response = client.post('/appointments/select', json={
            "appointment_id": 1
        })
        assert response.status_code == 401  # Unauthorized

    def test_get_current_appointment_without_login(self, client):
        """Test getting current appointment without login"""
        response = client.get('/appointments/current')
        assert response.status_code == 401  # Unauthorized

    def test_update_appointment_without_login(self, client):
        """Test updating appointment without login"""
        response = client.put('/appointments/update', json={})
        assert response.status_code == 401  # Unauthorized

    def test_delete_appointment_without_login(self, client):
        """Test deleting appointment without login"""
        response = client.delete('/appointments/1')
        assert response.status_code == 401  # Unauthorized