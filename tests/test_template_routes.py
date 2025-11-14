import pytest

class TestTemplateRoutes:
    """Test template serving routes."""
    
    def test_index_redirect(self, client):
        """Test root URL redirect."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/appointment.html' in response.location

    def test_public_pages_accessible(self, client):
        """Test that public pages are accessible."""
        public_pages = [
            '/login.html',
            '/signup.html',
            '/appointment.html'
        ]
        
        for page in public_pages:
            response = client.get(page)
            assert response.status_code == 200

    def test_view_appointments_accessible(self, auth_client):
        """Test view appointments page with auth."""
        response = auth_client.get('/viewAppointment/search')
        assert response.status_code == 200

    def test_update_appointment_requires_auth(self, client):
        """Test update appointment page requires authentication."""
        response = client.get('/updateAppointment.html')
        assert response.status_code == 302
        assert '/login.html' in response.location

    def test_update_appointment_requires_selection(self, auth_client):
        """Test update appointment page requires selected appointment."""
        with auth_client.session_transaction() as session:
            session.pop('selected_appointment', None)
        
        response = auth_client.get('/updateAppointment.html')
        assert response.status_code == 302
        assert '/viewAppointment/search' in response.location