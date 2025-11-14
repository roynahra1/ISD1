import pytest
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    os.environ['TESTING'] = 'True'
    yield
    # Cleanup
    if 'TESTING' in os.environ:
        del os.environ['TESTING']

@pytest.fixture
def app():
    """Create and configure a Flask app for testing"""
    from app import create_app
    
    app = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False
    })
    
    yield app

@pytest.fixture
def client(app):
    """Create a test client for the app"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create a CLI runner for the app"""
    return app.test_cli_runner()