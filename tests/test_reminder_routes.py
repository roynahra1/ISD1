import pytest
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import date

# Add the parent directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the routes directory
from routes.reminder_routes import reminder_bp, init_reminder_service, get_db_connection, get_all_owners_with_cars, send_reminder_email, send_monthly_reminders


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
    
    # Register the blueprint
    app.register_blueprint(reminder_bp)
    
    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def sample_owner_data():
    """Sample owner data for testing"""
    return [
        {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+961123456",
            "cars": [
                {
                    "plate": "ABC123",
                    "model": "Toyota Camry",
                    "year": 2020,
                    "next_oil_change": "2024-02-01"
                }
            ]
        }
    ]


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('routes.reminder_routes.mysql.connector.connect') as mock_conn:
        mock_connection = MagicMock()
        mock_conn.return_value = mock_connection
        yield mock_connection


@pytest.fixture
def mock_db_cursor(mock_db_connection):
    """Mock database cursor"""
    mock_cursor = MagicMock()
    mock_db_connection.cursor.return_value = mock_cursor
    mock_db_connection.is_connected.return_value = True
    return mock_cursor


# ===============================
# DATABASE CONNECTION TESTS
# ===============================

@patch('routes.reminder_routes.mysql.connector.connect')
def test_get_db_connection_success(mock_connect):
    """Test successful database connection"""
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    
    connection = get_db_connection()
    
    assert connection == mock_conn
    mock_connect.assert_called_once()


@patch('routes.reminder_routes.mysql.connector.connect')
def test_get_db_connection_error(mock_connect):
    """Test database connection error"""
    # Use a specific mysql.connector.Error instead of generic Exception
    import mysql.connector
    mock_connect.side_effect = mysql.connector.Error("Connection failed")
    
    connection = get_db_connection()
    
    assert connection is None


# ===============================
# INITIALIZATION TESTS
# ===============================

@patch.dict('os.environ', {}, clear=True)
def test_init_reminder_service_without_mail(app):
    """Test reminder service initialization without mail credentials"""
    init_reminder_service(app)
    
    assert app.config["MAIL_ENABLED"] == False


# ===============================
# DATABASE QUERY TESTS
# ===============================

@patch('routes.reminder_routes.get_db_connection')
def test_get_all_owners_with_cars_success(mock_get_conn, mock_db_connection, mock_db_cursor):
    """Test successful retrieval of owners with cars"""
    # Mock database response
    mock_db_cursor.fetchall.return_value = [
        {
            "Owner_ID": 1,
            "Owner_Name": "John Doe",
            "Owner_Email": "john@example.com",
            "PhoneNUMB": "+961123456",
            "Car_plate": "ABC123",
            "Model": "Toyota Camry",
            "Year": 2020,
            "Next_Oil_Change": "2024-02-01"
        }
    ]
    mock_get_conn.return_value = mock_db_connection
    
    owners = get_all_owners_with_cars()
    
    assert len(owners) == 1
    assert owners[0]["name"] == "John Doe"
    assert owners[0]["email"] == "john@example.com"
    assert len(owners[0]["cars"]) == 1
    assert owners[0]["cars"][0]["plate"] == "ABC123"


@patch('routes.reminder_routes.get_db_connection')
def test_get_all_owners_with_cars_no_owners(mock_get_conn, mock_db_connection, mock_db_cursor):
    """Test retrieval when no owners found"""
    mock_db_cursor.fetchall.return_value = []
    mock_get_conn.return_value = mock_db_connection
    
    owners = get_all_owners_with_cars()
    
    assert owners == []


@patch('routes.reminder_routes.get_db_connection')
def test_get_all_owners_with_cars_database_error(mock_get_conn, mock_db_connection, mock_db_cursor):
    """Test retrieval when database query fails"""
    mock_db_cursor.execute.side_effect = Exception("Query failed")
    mock_get_conn.return_value = mock_db_connection
    
    owners = get_all_owners_with_cars()
    
    assert owners == []


@patch('routes.reminder_routes.get_db_connection')
def test_get_all_owners_with_cars_no_connection(mock_get_conn):
    """Test retrieval when no database connection"""
    mock_get_conn.return_value = None
    
    owners = get_all_owners_with_cars()
    
    assert owners == []


# ===============================
# EMAIL SENDING TESTS (WITH APP CONTEXT)
# ===============================

def test_send_reminder_email_disabled(app, sample_owner_data):
    """Test email sending when mail is disabled"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = False
        
        result = send_reminder_email(sample_owner_data[0])
        
        assert result == True  # Returns True when disabled


@patch('routes.reminder_routes.mail')
def test_send_reminder_email_failure(mock_mail, app, sample_owner_data):
    """Test email sending failure"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_mail.send.side_effect = Exception("SMTP error")
        
        result = send_reminder_email(sample_owner_data[0])
        
        assert result == False


# ===============================
# MONTHLY REMINDERS TESTS (WITH APP CONTEXT)
# ===============================

@patch('routes.reminder_routes.get_all_owners_with_cars')
@patch('routes.reminder_routes.send_reminder_email')
def test_send_monthly_reminders_success(mock_send_email, mock_get_owners, app, sample_owner_data):
    """Test successful monthly reminders"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_get_owners.return_value = sample_owner_data
        mock_send_email.return_value = True
        
        result = send_monthly_reminders()
        
        assert result["success"] == True
        assert result["total"] == 1
        assert result["emails_sent"] == 1
        assert result["failed"] == 0
        mock_send_email.assert_called_once()


@patch('routes.reminder_routes.get_all_owners_with_cars')
def test_send_monthly_reminders_no_owners(mock_get_owners, app):
    """Test monthly reminders when no owners found"""
    with app.app_context():
        mock_get_owners.return_value = []
        
        result = send_monthly_reminders()
        
        assert result["success"] == False
        assert "No owners found" in result["message"]
        assert result["emails_sent"] == 0


@patch('routes.reminder_routes.get_all_owners_with_cars')
@patch('routes.reminder_routes.send_reminder_email')
def test_send_monthly_reminders_partial_failure(mock_send_email, mock_get_owners, app, sample_owner_data):
    """Test monthly reminders with partial email failures"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_get_owners.return_value = sample_owner_data * 2  # Two owners
        mock_send_email.side_effect = [True, False]  # One success, one failure
        
        result = send_monthly_reminders()
        
        assert result["success"] == True
        assert result["total"] == 2
        assert result["emails_sent"] == 1
        assert result["failed"] == 1


# ===============================
# ROUTE TESTS
# ===============================

@patch('routes.reminder_routes.send_monthly_reminders')
def test_trigger_reminders_route(mock_send_reminders, client):
    """Test the trigger reminders route"""
    mock_send_reminders.return_value = {
        "success": True,
        "total": 5,
        "emails_sent": 5,
        "failed": 0
    }
    
    response = client.post('/api/reminders/send')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] == True
    assert data["total"] == 5


@patch('routes.reminder_routes.get_all_owners_with_cars')
def test_test_reminders_route(mock_get_owners, client, app):
    """Test the test reminders route"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_get_owners.return_value = [{"name": "Test Owner"}]
        
        response = client.get('/api/reminders/test')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ready"
        assert data["owners_found"] == 1
        assert data["mail_enabled"] == True


def test_health_check_route(client):
    """Test the health check route"""
    response = client.get('/api/reminders/health')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "email_reminders"


# ===============================
# EDGE CASE TESTS (WITH APP CONTEXT)
# ===============================

@patch('routes.reminder_routes.get_all_owners_with_cars')
@patch('routes.reminder_routes.send_reminder_email')
def test_owner_with_multiple_cars(mock_send_email, mock_get_owners, app):
    """Test owner with multiple cars"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_get_owners.return_value = [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+961123456",
                "cars": [
                    {
                        "plate": "ABC123",
                        "model": "Toyota Camry",
                        "year": 2020,
                        "next_oil_change": "2024-02-01"
                    },
                    {
                        "plate": "XYZ789",
                        "model": "Honda Civic",
                        "year": 2019,
                        "next_oil_change": None
                    }
                ]
            }
        ]
        mock_send_email.return_value = True
        
        result = send_monthly_reminders()
        
        assert result["success"] == True
        assert result["total"] == 1


@patch('routes.reminder_routes.get_all_owners_with_cars')
@patch('routes.reminder_routes.send_reminder_email')
def test_owner_with_no_cars(mock_send_email, mock_get_owners, app):
    """Test owner with no cars"""
    with app.app_context():
        app.config["MAIL_ENABLED"] = True
        mock_get_owners.return_value = [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+961123456",
                "cars": []  # No cars
            }
        ]
        mock_send_email.return_value = True
        
        result = send_monthly_reminders()
        
        assert result["success"] == True
        assert result["total"] == 1


# ===============================
# ADDITIONAL COVERAGE TESTS
# ===============================

def test_init_reminder_service_scheduler_already_running(app):
    """Test that scheduler is not started twice"""
    # Mock that scheduler already exists
    with patch('routes.reminder_routes.scheduler', MagicMock()):
        with patch('routes.reminder_routes.BackgroundScheduler') as mock_scheduler:
            init_reminder_service(app)
            
            # Should not create new scheduler if one exists
            mock_scheduler.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])