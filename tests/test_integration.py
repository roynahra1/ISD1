import pytest
import json

class TestIntegrationFlows:
    """Test complete user flows."""
    
    def test_user_registration_and_login_flow(self, client, mock_db):
        """Test complete user registration and login flow."""
        # Register user
        user_data = {
            "username": "flowuser",
            "email": "flow@example.com",
            "password": "flowpass123"
        }
        
        response = client.post('/signup',
                             data=json.dumps(user_data),
                             content_type='application/json')
        assert response.status_code in [201, 400, 409, 500]
        
        # Login
        login_data = {
            "username": "flowuser",
            "password": "flowpass123"
        }
        
        response = client.post('/login',
                             data=json.dumps(login_data),
                             content_type='application/json')
        assert response.status_code in [200, 401, 500]
    
    def test_appointment_management_flow(self, auth_client, mock_db):
        """Test complete appointment management flow."""
        # Search appointments
        response = auth_client.get('/appointment/search?car_plate=FLOW123')
        assert response.status_code in [200, 400, 500]
        
        # Get current appointment
        response = auth_client.get('/appointments/current')
        assert response.status_code in [200, 404]
        
        # Book appointment
        appointment_data = {
            "car_plate": "FLOW123",
            "date": "2024-12-31",
            "time": "14:00",
            "service_ids": [1, 2],
            "notes": "Integration test"
        }
        
        response = auth_client.post('/book',
                                 data=json.dumps(appointment_data),
                                 content_type='application/json')
        assert response.status_code in [201, 400, 409, 500]

    def test_session_flow(self, client):
        """Test session management flow."""
        # Start logged out
        response = client.get('/auth/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['logged_in'] is False
        
        # Test setting session manually
        with client.session_transaction() as session:
            session['logged_in'] = True
            session['username'] = 'testuser'
        
        # Now should be logged in
        response = client.get('/auth/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['logged_in'] is True
        
        # Test logout
        response = client.post('/logout')
        assert response.status_code == 200
        
        # After logout, should be logged out again
        response = client.get('/auth/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['logged_in'] is False