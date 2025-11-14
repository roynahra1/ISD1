import pytest
import mysql.connector
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db_config

def setup_test_database():
    """Setup test database with required tables"""
    config = get_db_config()
    
    # Connect without specifying database to create it
    config_no_db = config.copy()
    config_no_db.pop('database', None)
    
    conn = mysql.connector.connect(**config_no_db)
    cursor = conn.cursor()
    
    try:
        # Create test database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config['database']}")
        cursor.execute(f"USE {config['database']}")
        
        # Create minimal tables for testing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(255) UNIQUE,
                Email VARCHAR(255) UNIQUE,
                Password VARCHAR(255)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointment (
                Appointment_id INT AUTO_INCREMENT PRIMARY KEY,
                Date DATE,
                Time TIME,
                Notes TEXT,
                Car_plate VARCHAR(20)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service (
                Service_ID INT AUTO_INCREMENT PRIMARY KEY,
                Service_Type VARCHAR(255)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointment_service (
                Appointment_id INT,
                Service_ID INT,
                FOREIGN KEY (Appointment_id) REFERENCES appointment(Appointment_id),
                FOREIGN KEY (Service_ID) REFERENCES service(Service_ID)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS car (
                Car_plate VARCHAR(20) PRIMARY KEY,
                Model VARCHAR(255),
                Year INT,
                VIN VARCHAR(255),
                Next_Oil_Change DATE,
                Owner_id INT
            )
        """)
        
        # Insert test data
        cursor.execute("INSERT IGNORE INTO service (Service_ID, Service_Type) VALUES (1, 'Oil Change')")
        cursor.execute("INSERT IGNORE INTO service (Service_ID, Service_Type) VALUES (2, 'Tire Rotation')")
        cursor.execute("INSERT IGNORE INTO service (Service_ID, Service_Type) VALUES (3, 'Brake Inspection')")
        cursor.execute("INSERT IGNORE INTO service (Service_ID, Service_Type) VALUES (4, 'Battery Check')")
        
        conn.commit()
        print("Test database setup completed")
        
    except Exception as e:
        print(f"Error setting up test database: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Setup test database before running tests"""
    setup_test_database()
    yield
    # Optional: cleanup after tests