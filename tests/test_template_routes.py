import pytest

class TestTemplateRoutes:
    
    def test_login_page(self, client):
        """Test login page loads"""
        response = client.get('/login.html')
        assert response.status_code == 200
    
    def test_appointment_page(self, client):
        """Test appointment page loads"""
        response = client.get('/appointment.html')
        assert response.status_code == 200
    
    def test_signup_page(self, client):
        """Test signup page loads"""
        response = client.get('/signup.html')
        assert response.status_code == 200
    
    def test_view_appointment_page(self, client):
        """Test view appointment page loads"""
        response = client.get('/viewAppointment/search')
        assert response.status_code == 200
    
    def test_update_appointment_page_redirect_when_not_logged_in(self, client):
        """Test update appointment page redirects when not logged in"""
        response = client.get('/updateAppointment.html')
        # Should redirect to login when not authenticated
        assert response.status_code in [302, 401, 404]
    
    def test_update_appointment_page_with_session(self, client):
        """Test update appointment page with proper session"""
        with client.session_transaction() as session:
            session['logged_in'] = True
            session['selected_appointment'] = {'Appointment_id': 1}
        
        response = client.get('/updateAppointment.html')
        # Should work with proper session
        assert response.status_code == 200