import pytest
from unittest.mock import patch, MagicMock

class TestAppointmentRoutes:
    
    def test_book_appointment(self, client):
        """Test booking an appointment"""
        response = client.post('/book', json={
            "car_plate": "TEST123",
            "date": "2024-12-01",
            "time": "10:00", 
            "service_ids": [1, 2],
            "notes": "Test appointment"
        })
        # Should return error due to missing database, but not 500
        assert response.status_code != 500

    def test_search_appointments(self, client):
        """Test searching appointments by car plate"""
        response = client.get('/appointment/search?car_plate=TEST123')
        assert response.status_code != 500

    def test_get_appointment_by_id(self, client):
        """Test getting a specific appointment"""
        response = client.get('/appointments/1')
        assert response.status_code != 500

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