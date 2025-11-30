import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock, Mock

# Add the parent directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from after_service import after_service_bp, get_db_config, get_connection


# ===============================
# TEST FIXTURES
# ===============================

@pytest.fixture
def app():
    """Create a Flask app for testing"""
    from flask import Flask
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register the blueprint with the correct URL prefix
    app.register_blueprint(after_service_bp, url_prefix='/after-service')
    
    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('after_service.mysql.connector.connect') as mock_conn:
        mock_connection = MagicMock()
        mock_conn.return_value = mock_connection
        yield mock_connection


@pytest.fixture
def mock_db_cursor(mock_db_connection):
    """Mock database cursor"""
    mock_cursor = MagicMock()
    mock_db_connection.cursor.return_value = mock_cursor
    mock_db_connection.commit.return_value = None
    mock_db_connection.rollback.return_value = None
    return mock_cursor


# ===============================
# CONFIGURATION TESTS
# ===============================

def test_get_db_config_production():
    """Test database configuration for production"""
    # Clear any existing TESTING environment variable
    if 'TESTING' in os.environ:
        del os.environ['TESTING']
    
    with patch.dict('os.environ', {
        'DB_HOST': 'prod-host',
        'DB_USER': 'prod-user', 
        'DB_PASSWORD': 'prod-pass',
        'DB_NAME': 'prod-db'
    }):
        config = get_db_config()
        
        assert config['host'] == 'prod-host'
        assert config['user'] == 'prod-user'
        assert config['password'] == 'prod-pass'
        assert config['database'] == 'prod-db'


def test_get_db_config_testing():
    """Test database configuration for testing environment"""
    # Set testing environment
    os.environ['TESTING'] = 'True'
    
    with patch.dict('os.environ', {
        'DB_HOST': 'test-host',
        'DB_USER': 'test-user',
        'DB_PASSWORD': 'test-pass',
        'TEST_DB_NAME': 'test-db'
    }):
        config = get_db_config()
        
        assert config['database'] == 'test-db'
    
    # Clean up
    del os.environ['TESTING']


def test_get_db_config_defaults():
    """Test database configuration with defaults"""
    # Clear environment to test defaults
    env_vars_to_clear = ['TESTING', 'DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME', 'TEST_DB_NAME']
    saved_env = {}
    
    for var in env_vars_to_clear:
        if var in os.environ:
            saved_env[var] = os.environ[var]
            del os.environ[var]
    
    try:
        config = get_db_config()
        
        assert config['host'] == 'localhost'
        assert config['user'] == 'root'
        assert config['password'] == ''
        assert config['database'] == 'isd'
    finally:
        # Restore environment
        for var, value in saved_env.items():
            os.environ[var] = value


# ===============================
# HEALTH CHECK TESTS
# ===============================

@patch('after_service.get_connection')
def test_health_check_success(mock_get_connection, client):
    """Test health check endpoint when database is connected"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [1]
    
    response = client.get('/after-service/api/health')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['database'] == 'connected'
    assert 'After-service routes are healthy' in response.json['message']


@patch('after_service.get_connection')
def test_health_check_failure(mock_get_connection, client):
    """Test health check endpoint when database is disconnected"""
    mock_get_connection.side_effect = Exception("Connection failed")
    
    response = client.get('/after-service/api/health')
    
    assert response.status_code == 500
    assert response.json['status'] == 'error'
    assert response.json['database'] == 'disconnected'


# ===============================
# CAR INFO TESTS
# ===============================

@patch('after_service.get_connection')
def test_get_car_info_success(mock_get_connection, client):
    """Test getting car information successfully"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_car_data = {
        'Car_plate': 'ABC123',
        'Model': 'Toyota Camry',
        'Year': 2020,
        'VIN': '1HGCM82633A123456',
        'Next_Oil_Change': '2024-02-01',
        'Owner_Name': 'John Doe',
        'Owner_Email': 'john@example.com',
        'PhoneNUMB': '+961123456'
    }
    mock_cursor.fetchone.return_value = mock_car_data
    
    response = client.get('/after-service/api/car/ABC123')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['data']['Car_plate'] == 'ABC123'
    assert response.json['data']['Model'] == 'Toyota Camry'


@patch('after_service.get_connection')
def test_get_car_info_not_found(mock_get_connection, client):
    """Test getting car information when car not found"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchone.return_value = None
    
    response = client.get('/after-service/api/car/NOTFOUND')
    
    assert response.status_code == 404
    assert response.json['status'] == 'error'
    assert 'Car not found' in response.json['message']


@patch('after_service.get_connection')
def test_get_car_info_database_error(mock_get_connection, client):
    """Test getting car information with database error"""
    mock_get_connection.side_effect = Exception("Database error")
    
    response = client.get('/after-service/api/car/ABC123')
    
    assert response.status_code == 500
    assert response.json['status'] == 'error'
    assert 'Database error' in response.json['message']


# ===============================
# UPDATE CAR SERVICE TESTS
# ===============================

@patch('after_service.get_connection')
def test_update_car_service_success(mock_get_connection, client):
    """Test successful car service update"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 123
    
    service_data = {
        'car_plate': 'ABC123',
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456',
        'service_date': '2024-01-15',
        'mileage': 50000,
        'last_oil_change': '2024-01-15',
        'next_oil_change': '2024-07-15',
        'notes': 'Regular maintenance',
        'services_performed': [1, 2, 3]
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['history_id'] == 123
    assert 'successfully' in response.json['message']


def test_update_car_service_missing_plate(client):
    """Test car service update with missing car plate"""
    service_data = {
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456'
        # Missing car_plate
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 400
    assert response.json['status'] == 'error'
    assert 'Car plate is required' in response.json['message']


@patch('after_service.get_connection')
def test_update_car_service_database_error(mock_get_connection, client):
    """Test car service update with database error"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("Database constraint error")
    
    service_data = {
        'car_plate': 'ABC123',
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456'
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 500
    assert response.json['status'] == 'error'


@patch('after_service.get_connection')
def test_update_car_service_primary_key_error(mock_get_connection, client):
    """Test car service update with primary key conflict"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Create a specific error that matches the error handling in your code
    class MockMySQLError(Exception):
        def __str__(self):
            return "Error 1062: Duplicate entry for key 'PRIMARY'"
    
    mock_cursor.execute.side_effect = MockMySQLError("Error 1062: Duplicate entry for key 'PRIMARY'")
    
    service_data = {
        'car_plate': 'ABC123',
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456'
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 500
    assert 'conflict' in response.json['message'].lower()


# ===============================
# SERVICE HISTORY TESTS
# ===============================

@patch('after_service.get_connection')
def test_get_service_history_success(mock_get_connection, client):
    """Test getting service history successfully"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_service_history = [
        {
            'History_ID': 1,
            'Service_Date': '2024-01-15',
            'Mileage': 50000,
            'Last_Oil_Change': '2024-01-15',
            'Notes': 'Oil change',
            'Services_Performed': 'Oil Change, Tire Rotation'
        }
    ]
    mock_cursor.fetchall.return_value = mock_service_history
    
    response = client.get('/after-service/api/service-history/ABC123')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['count'] == 1
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['History_ID'] == 1


@patch('after_service.get_connection')
def test_get_service_history_empty(mock_get_connection, client):
    """Test getting service history when no records exist"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchall.return_value = []
    
    response = client.get('/after-service/api/service-history/ABC123')
    
    assert response.status_code == 200
    assert response.json['count'] == 0
    assert len(response.json['data']) == 0


# ===============================
# ALL CARS TESTS
# ===============================

@patch('after_service.get_connection')
def test_get_all_cars_success(mock_get_connection, client):
    """Test getting all cars successfully"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cars = [
        {
            'Car_plate': 'ABC123',
            'Model': 'Toyota Camry',
            'Year': 2020,
            'VIN': '1HGCM82633A123456',
            'Next_Oil_Change': '2024-02-01',
            'Owner_Name': 'John Doe',
            'Owner_Email': 'john@example.com',
            'PhoneNUMB': '+961123456',
            'Last_Service_Date': '2024-01-15'
        }
    ]
    mock_cursor.fetchall.return_value = mock_cars
    
    response = client.get('/after-service/api/all-cars')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['count'] == 1
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['Car_plate'] == 'ABC123'


# ===============================
# UPCOMING SERVICES TESTS
# ===============================

@patch('after_service.get_connection')
def test_get_upcoming_services_success(mock_get_connection, client):
    """Test getting upcoming services successfully"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_upcoming_services = [
        {
            'Car_plate': 'ABC123',
            'Model': 'Toyota Camry',
            'Next_Oil_Change': '2024-02-01',
            'Owner_Name': 'John Doe',
            'PhoneNUMB': '+961123456',
            'Days_Until_Service': 15
        }
    ]
    mock_cursor.fetchall.return_value = mock_upcoming_services
    
    response = client.get('/after-service/api/upcoming-services')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert response.json['count'] == 1
    assert response.json['data'][0]['Car_plate'] == 'ABC123'


# ===============================
# DASHBOARD STATS TESTS
# ===============================

@patch('after_service.get_connection')
def test_get_dashboard_stats_success(mock_get_connection, client):
    """Test getting dashboard statistics successfully"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock multiple fetchone calls for different stats
    mock_cursor.fetchone.side_effect = [
        {'total_cars': 50},
        {'services_this_month': 15},
        {'upcoming_services': 3},
        {'recent_services': 8}
    ]
    
    response = client.get('/after-service/api/dashboard-stats')
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'
    assert 'data' in response.json
    assert response.json['data']['total_cars'] == 50
    assert response.json['data']['services_this_month'] == 15
    assert response.json['data']['upcoming_services'] == 3
    assert response.json['data']['recent_services'] == 8


# ===============================
# TEMPLATE ROUTE TESTS
# ===============================

@patch('after_service.render_template')
def test_after_service_form(mock_render, client):
    """Test after service form template route"""
    mock_render.return_value = "<html>Form Content</html>"
    
    response = client.get('/after-service/after-service')
    
    assert response.status_code == 200
    mock_render.assert_called_once_with('after_service_form.html')


# ===============================
# ERROR HANDLING TESTS
# ===============================

@patch('after_service.get_connection')
def test_general_exception_handling(mock_get_connection, client):
    """Test general exception handling in routes"""
    mock_get_connection.side_effect = Exception("General error")
    
    response = client.get('/after-service/api/all-cars')
    
    assert response.status_code == 500
    assert response.json['status'] == 'error'
    assert 'Database error' in response.json['message']


def test_invalid_json_post(client):
    """Test handling invalid JSON in POST requests"""
    # Send invalid JSON
    response = client.post(
        '/after-service/api/update-car-service',
        data='invalid json',
        content_type='application/json'
    )
    
    # This should be 400 for bad request
    assert response.status_code == 400


# ===============================
# EDGE CASE TESTS
# ===============================

@patch('after_service.get_connection')
def test_update_car_service_no_services_performed(mock_get_connection, client):
    """Test car service update with no services performed"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 124
    
    service_data = {
        'car_plate': 'ABC123',
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456',
        'service_date': '2024-01-15',
        'mileage': 50000
        # No services_performed field
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'


@patch('after_service.get_connection')
def test_update_car_service_empty_services(mock_get_connection, client):
    """Test car service update with empty services list"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 125
    
    service_data = {
        'car_plate': 'ABC123',
        'model': 'Toyota Camry',
        'year': 2020,
        'vin': '1HGCM82633A123456',
        'service_date': '2024-01-15',
        'mileage': 50000,
        'services_performed': []  # Empty list
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'


@patch('after_service.get_connection')
def test_update_car_service_null_values(mock_get_connection, client):
    """Test car service update with null/empty values"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.lastrowid = 126
    
    service_data = {
        'car_plate': 'ABC123',
        'model': '',  # Empty string
        'year': None,  # None value
        'vin': '1HGCM82633A123456',
        'service_date': '2024-01-15'
        # Missing mileage, notes, etc.
    }
    
    response = client.post('/after-service/api/update-car-service', json=service_data)
    
    assert response.status_code == 200
    assert response.json['status'] == 'success'


# ===============================
# DATABASE CONNECTION TESTS
# ===============================

@patch('after_service.mysql.connector.connect')
def test_get_connection_success(mock_connect):
    """Test successful database connection"""
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    
    connection = get_connection()
    
    assert connection == mock_conn
    mock_connect.assert_called_once()


@patch('after_service.mysql.connector.connect')
def test_get_connection_error(mock_connect):
    """Test database connection error"""
    mock_connect.side_effect = Exception("Connection failed")
    
    with pytest.raises(Exception, match="Connection failed"):
        get_connection()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])