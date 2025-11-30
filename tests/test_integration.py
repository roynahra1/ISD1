import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasicIntegration:
    """Basic integration tests that don't require full app setup"""
    
    def test_import_modules(self):
        """Test that core modules can be imported without errors"""
        # Test importing route modules
        try:
            from routes import auth_routes, appointment_routes, car_routes
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import route modules: {e}")
    
    def test_blueprint_creation(self):
        """Test that blueprints can be created"""
        try:
            from routes.auth_routes import auth_bp
            from routes.appointment_routes import appointment_bp
            from routes.car_routes import car_bp
            from routes.mechanic_routes import mechanic_bp
            
            assert auth_bp.name == 'auth'
            assert appointment_bp.name == 'appointments'  # Fixed: actual name is 'appointments'
            assert car_bp.name == 'car'
            assert mechanic_bp.name == 'mechanic'
        except Exception as e:
            pytest.fail(f"Failed to create blueprints: {e}")
    
    @patch('routes.auth_routes.get_connection')
    def test_cross_module_interaction(self, mock_db):
        """Test interaction between different modules"""
        # Mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Import and test auth functionality
        from routes.auth_routes import auth_bp
        from flask import Flask
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        app.register_blueprint(auth_bp)
        
        with app.test_client() as client:
            # Test auth status endpoint
            response = client.get('/auth/status')
            assert response.status_code == 200
    
    def test_utility_functions(self):
        """Test utility functions work together"""
        try:
            from utils.helpers import serialize
            from utils.database import get_connection
            
            # Test that utility modules can be imported
            assert callable(serialize)
        except Exception as e:
            pytest.fail(f"Utility functions test failed: {e}")
    
    def test_session_consistency(self):
        """Test session management across different routes"""
        from flask import Flask, session
        from routes.auth_routes import auth_bp
        from routes.appointment_routes import appointment_bp
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        app.register_blueprint(auth_bp)
        app.register_blueprint(appointment_bp)
        
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['logged_in'] = True
                sess['username'] = 'integration_user'
            
            # Test that session is accessible across different routes
            response1 = client.get('/auth/status')
            assert response1.status_code == 200
            
            # Session should persist between requests
            with client.session_transaction() as sess:
                assert sess.get('logged_in') == True
                assert sess.get('username') == 'integration_user'