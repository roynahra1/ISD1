import pytest
import sys
import os
from unittest.mock import patch, MagicMock, Mock

# Add the parent directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.auth_routes import auth_bp


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
    app.register_blueprint(auth_bp)
    
    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def authenticated_session(client):
    """Create an authenticated session"""
    with client.session_transaction() as sess:
        sess['logged_in'] = True
        sess['username'] = 'testuser'
    return client


@pytest.fixture
def mechanic_authenticated_session(client):
    """Create an authenticated mechanic session"""
    with client.session_transaction() as sess:
        sess['mechanic_logged_in'] = True
        sess['mechanic_username'] = 'mechanic1'
        sess['mechanic_user_type'] = 'mechanic'
    return client


@pytest.fixture
def admin_authenticated_session(client):
    """Create an authenticated admin session"""
    with client.session_transaction() as sess:
        sess['mechanic_logged_in'] = True
        sess['mechanic_username'] = 'admin'
        sess['mechanic_user_type'] = 'admin'
    return client


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('routes.auth_routes.get_connection') as mock_conn:
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
# TEMPLATE ROUTES TESTS (FIXED)
# ===============================

@patch('routes.auth_routes.render_template')
def test_login_page(mock_render, client):
    """Test login page loads"""
    mock_render.return_value = '<html>Login Page</html>'
    response = client.get('/login.html')
    assert response.status_code == 200
    mock_render.assert_called_once_with('login.html')


@patch('routes.auth_routes.render_template')
def test_signup_page(mock_render, client):
    """Test signup page loads"""
    mock_render.return_value = '<html>Signup Page</html>'
    response = client.get('/signup.html')
    assert response.status_code == 200
    mock_render.assert_called_once_with('signup.html')


@patch('routes.auth_routes.render_template')
def test_mechanic_login_page(mock_render, client):
    """Test mechanic login page loads"""
    mock_render.return_value = '<html>Mechanic Login Page</html>'
    response = client.get('/mechanic/login.html')
    assert response.status_code == 200
    mock_render.assert_called_once_with('mechanic_login.html')


@patch('routes.auth_routes.render_template')
def test_admin_login_page(mock_render, client):
    """Test admin login page loads"""
    mock_render.return_value = '<html>Admin Login Page</html>'
    response = client.get('/admin/login.html')
    assert response.status_code == 200
    mock_render.assert_called_once_with('admin_login.html')


# ===============================
# REGULAR AUTHENTICATION TESTS
# ===============================

@patch('routes.auth_routes.get_connection')
def test_login_success(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test successful login"""
    # Mock database response as a dictionary (matches dictionary=True cursor)
    mock_db_cursor.fetchone.return_value = {
        'Username': 'testuser',
        'Password': 'hashed_password',
        'Email': 'testuser@example.com',
        'PhoneNUMB': None,
        'Owner_ID': None,
        'Owner_Name': None,
        'Owner_Email': None,
        'Owner_Phone': None
    }
    mock_get_conn.return_value = mock_db_connection
    
    # Mock password verification
    with patch('routes.auth_routes.check_password_hash', return_value=True):
        response = client.post('/login', json={
            "username": "testuser",
            "password": "password123"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['message'] == 'Login successful'


@patch('routes.auth_routes.get_connection')
def test_login_user_not_found(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test login with non-existent user"""
    mock_db_cursor.fetchone.return_value = None
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/login', json={
        "username": "nonexistent",
        "password": "password"
    })
    
    assert response.status_code == 401
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Invalid username or password' in data['message']


@patch('routes.auth_routes.get_connection')
def test_login_wrong_password(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test login with wrong password"""
    mock_db_cursor.fetchone.return_value = ('hashed_password',)
    mock_get_conn.return_value = mock_db_connection
    
    # Mock password verification failure
    with patch('routes.auth_routes.check_password_hash', return_value=False):
        response = client.post('/login', json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'


def test_login_missing_fields(client):
    """Test login with missing fields"""
    # Missing username
    response = client.post('/login', json={
        "password": "password123"
    })
    assert response.status_code == 400
    
    # Missing password
    response = client.post('/login', json={
        "username": "testuser"
    })
    assert response.status_code == 400
    
    # Empty strings
    response = client.post('/login', json={
        "username": "",
        "password": "password123"
    })
    assert response.status_code == 400


@patch('routes.auth_routes.get_connection')
def test_login_database_error(mock_get_conn, client):
    """Test login with database error"""
    mock_get_conn.side_effect = Exception("Database connection failed")
    
    response = client.post('/login', json={
        "username": "testuser",
        "password": "password123"
    })
    
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'error'


@patch('routes.auth_routes.get_connection')
def test_signup_success(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test successful signup"""
    # Mock database responses - no existing user
    mock_db_cursor.fetchone.side_effect = [None, None]
    mock_get_conn.return_value = mock_db_connection
    
    with patch('routes.auth_routes.generate_password_hash', return_value='hashed_password'):
        response = client.post('/signup', json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123"
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['status'] == 'success'
        # Signup creates both account and owner profile
        assert 'owner_id' in data


@patch('routes.auth_routes.get_connection')
def test_signup_username_exists(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test signup with existing username"""
    # Mock that username already exists
    mock_db_cursor.fetchone.side_effect = [('exists',), None]
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/signup', json={
        "username": "existinguser",
        "email": "new@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 409
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Username already exists' in data['message']


@patch('routes.auth_routes.get_connection')
def test_signup_email_exists(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test signup with existing email"""
    # Mock that email already exists
    mock_db_cursor.fetchone.side_effect = [None, ('exists',)]
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/signup', json={
        "username": "newuser",
        "email": "existing@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 409
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Email already registered' in data['message']


def test_signup_missing_fields(client):
    """Test signup with missing fields"""
    # Missing username
    response = client.post('/signup', json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 400
    
    # Missing email
    response = client.post('/signup', json={
        "username": "testuser",
        "password": "password123"
    })
    assert response.status_code == 400
    
    # Missing password
    response = client.post('/signup', json={
        "username": "testuser",
        "email": "test@example.com"
    })
    assert response.status_code == 400
    
    # Empty strings
    response = client.post('/signup', json={
        "username": "",
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 400


def test_signup_short_password(client):
    """Test signup with short password"""
    response = client.post('/signup', json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "123"
    })
    
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Password must be at least 6 characters' in data['message']


@patch('routes.auth_routes.get_connection')
def test_signup_database_error(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test signup with database error"""
    # Mock database error during insert
    mock_db_cursor.fetchone.side_effect = [None, None]
    mock_db_cursor.execute.side_effect = Exception("Insert failed")
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/signup', json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'error'


def test_logout_success(client):
    """Test successful logout"""
    response = client.post('/logout')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['message'] == 'Logged out'


def test_auth_status_logged_in(authenticated_session):
    """Test auth status when logged in"""
    response = authenticated_session.get('/auth/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['logged_in'] == True
    assert data['username'] == 'testuser'


def test_auth_status_not_logged_in(client):
    """Test auth status when not logged in"""
    response = client.get('/auth/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['logged_in'] == False
    assert data['username'] is None


# ===============================
# MECHANIC AUTHENTICATION TESTS
# ===============================

@patch('routes.auth_routes.get_connection')
def test_mechanic_login_success_database(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test successful mechanic login from database"""
    # Mock database user found
    mock_db_cursor.fetchone.return_value = {'Username': 'mechanic1', 'Password': 'hashed_password'}
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/mechanic/login', json={
        "username": "mechanic1",
        "password": "password123"
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['message'] == 'Mechanic login successful'


@patch('routes.auth_routes.get_connection')
def test_mechanic_login_success_demo(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test successful mechanic login with demo credentials"""
    # Mock no user in database
    mock_db_cursor.fetchone.return_value = None
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/mechanic/login', json={
        "username": "mechanic1",
        "password": "12345"  # Demo password
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['message'] == 'Mechanic login successful'


@patch('routes.auth_routes.get_connection')
def test_mechanic_login_admin_redirect(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test mechanic login with admin user redirects to admin dashboard"""
    # Mock no user in database (use demo credentials)
    mock_db_cursor.fetchone.return_value = None
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/mechanic/login', json={
        "username": "admin",
        "password": "admin123"  # Demo password
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['redirect'] == '/mechanic/admin/dashboard'


@patch('routes.auth_routes.get_connection')
def test_mechanic_login_failure(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test mechanic login failure"""
    # Mock no user in database and wrong demo password
    mock_db_cursor.fetchone.return_value = None
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/mechanic/login', json={
        "username": "mechanic1",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
    data = response.get_json()
    assert data['status'] == 'error'


def test_mechanic_login_missing_fields(client):
    """Test mechanic login with missing fields"""
    response = client.post('/mechanic/login', json={
        "username": "mechanic1"
        # Missing password
    })
    assert response.status_code == 400


@patch('routes.auth_routes.get_connection')
def test_mechanic_login_database_error(mock_get_conn, client):
    """Test mechanic login with database error"""
    mock_get_conn.side_effect = Exception("Database error")
    
    response = client.post('/mechanic/login', json={
        "username": "mechanic1",
        "password": "password123"
    })
    
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'error'


def test_mechanic_logout_success(mechanic_authenticated_session):
    """Test successful mechanic logout"""
    response = mechanic_authenticated_session.post('/mechanic/logout')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['message'] == 'Logged out'


def test_mechanic_auth_status_logged_in(mechanic_authenticated_session):
    """Test mechanic auth status when logged in"""
    response = mechanic_authenticated_session.get('/mechanic/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['logged_in'] == True
    assert data['username'] == 'mechanic1'
    assert data['user_type'] == 'mechanic'


def test_mechanic_auth_status_not_logged_in(client):
    """Test mechanic auth status when not logged in"""
    response = client.get('/mechanic/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['logged_in'] == False


def test_admin_login_route(client):
    """Test admin login route redirects to mechanic login"""
    with patch('routes.auth_routes.mechanic_login') as mock_mechanic_login:
        mock_mechanic_login.return_value = ('mocked_response', 200)
        
        response = client.post('/admin/login', json={
            "username": "admin",
            "password": "admin123"
        })
        
        # Should call mechanic_login function
        mock_mechanic_login.assert_called_once()


def test_admin_logout_route(admin_authenticated_session):
    """Test admin logout route"""
    response = admin_authenticated_session.post('/admin/logout')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'


def test_admin_auth_status_logged_in(admin_authenticated_session):
    """Test admin auth status when logged in"""
    response = admin_authenticated_session.get('/admin/status')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['logged_in'] == True
    assert data['username'] == 'admin'
    assert data['user_type'] == 'admin'


# ===============================
# EDGE CASE TESTS (FIXED)
# ===============================

def test_login_no_json_data(client):
    """Test login with no JSON data"""
    response = client.post('/login', data="not json", content_type='application/json')
    # Could be 400, 415, or 500 depending on Flask version and error handling
    assert response.status_code in [400, 415, 500]


def test_signup_no_json_data(client):
    """Test signup with no JSON data"""
    response = client.post('/signup', data="not json", content_type='application/json')
    # Could be 400, 415, or 500 depending on Flask version and error handling
    assert response.status_code in [400, 415, 500]


def test_mechanic_login_no_json_data(client):
    """Test mechanic login with no JSON data"""
    response = client.post('/mechanic/login', data="not json", content_type='application/json')
    # Could be 400, 415, or 500 depending on Flask version and error handling
    assert response.status_code in [400, 415, 500]


def test_session_clearing_mechanic_login(client):
    """Test that mechanic login clears regular session"""
    # First set regular session
    with client.session_transaction() as sess:
        sess['logged_in'] = True
        sess['username'] = 'regularuser'
    
    # Mock mechanic login
    with patch('routes.auth_routes.get_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Use demo credentials
        
        response = client.post('/mechanic/login', json={
            "username": "mechanic1",
            "password": "12345"
        })
        
        assert response.status_code == 200
        
        # Check that regular session is cleared and mechanic session is set
        with client.session_transaction() as sess:
            assert sess.get('logged_in') is None  # Regular session cleared
            assert sess.get('mechanic_logged_in') == True  # Mechanic session set


# ===============================
# ADDITIONAL COVERAGE TESTS
# ===============================

@patch('routes.auth_routes.get_connection')
def test_login_unexpected_error(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test login with unexpected error"""
    mock_db_cursor.execute.side_effect = Exception("Unexpected error")
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/login', json={
        "username": "testuser",
        "password": "password123"
    })
    
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'error'


@patch('routes.auth_routes.get_connection')
def test_signup_unexpected_error(mock_get_conn, mock_db_connection, mock_db_cursor, client):
    """Test signup with unexpected error"""
    mock_db_cursor.fetchone.side_effect = Exception("Unexpected error")
    mock_get_conn.return_value = mock_db_connection
    
    response = client.post('/signup', json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123"
    })
    
    assert response.status_code == 500
    data = response.get_json()
    assert data['status'] == 'error'



def test_auth_status_exception_handling(client):
    """Test auth status with exception handling"""
    # This is hard to test directly, but we can verify the route exists
    response = client.get('/auth/status')
    assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])