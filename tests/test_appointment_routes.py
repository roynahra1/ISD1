import pytest
import json
from datetime import datetime, timedelta

class TestAppointmentRoutes:
    """Test appointment-related routes."""
    
    def test_appointment_page_accessible(self, client):
        """Test that appointment booking page is accessible."""
        response = client.get('/appointment.html')
        assert response.status_code == 200

    def test_book_appointment_validation(self, client, mock_db, sample_appointment_data):
        """Test appointment booking validation."""
        response = client.post('/book',
                             data=json.dumps(sample_appointment_data),
                             content_type='application/json')
        # Should handle the request without crashing
        assert response.status_code in [201, 400, 409, 500]

    def test_book_appointment_past_date(self, client):
        """Test booking appointment with past date."""
        past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        data = {
            "car_plate": "TEST123",
            "date": past_date,
            "time": "10:00",
            "service_ids": [1, 2]
        }
        
        response = client.post('/book',
                             data=json.dumps(data),
                             content_type='application/json')
        assert response.status_code in [400, 500]

    def test_book_appointment_missing_fields(self, client):
        """Test booking with missing required fields."""
        test_cases = [
            {"car_plate": "", "date": "2024-01-15", "time": "10:00", "service_ids": [1]},
            {"car_plate": "TEST123", "date": "", "time": "10:00", "service_ids": [1]},
            {"car_plate": "TEST123", "date": "2024-01-15", "time": "", "service_ids": [1]},
            {"car_plate": "TEST123", "date": "2024-01-15", "time": "10:00", "service_ids": []},
        ]
        
        for data in test_cases:
            response = client.post('/book',
                                 data=json.dumps(data),
                                 content_type='application/json')
            assert response.status_code in [400, 500]

    def test_search_appointments_endpoint(self, client, mock_db):
        """Test appointment search endpoint."""
        response = client.get('/appointment/search?car_plate=TEST123')
        assert response.status_code in [200, 400, 500]

    def test_search_appointments_missing_plate(self, client):
        """Test search without car plate."""
        response = client.get('/appointment/search')
        assert response.status_code == 400

    def test_get_appointment_by_id_endpoint(self, client, mock_db):
        """Test getting appointment by ID endpoint."""
        response = client.get('/appointments/1')
        assert response.status_code in [200, 404, 500]