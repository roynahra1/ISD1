#!/usr/bin/env python3
"""
Database setup script for ISD1 Appointment System
"""

import mysql.connector
from config import DB_CONFIG

def setup_database():
    """Create database and tables if they don't exist."""
    try:
        # Connect without specifying database first
        config = DB_CONFIG.copy()
        config.pop('database', None)
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        print("🗄️ Setting up database...")
        
        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS isd")
        print("✅ Database 'isd' created or already exists")
        
        # Switch to the database
        cursor.execute("USE isd")
        
        # Create tables
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS admin (
                id INT AUTO_INCREMENT PRIMARY KEY,
                Username VARCHAR(255) UNIQUE NOT NULL,
                Email VARCHAR(255) UNIQUE NOT NULL,
                Password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS car (
                Car_plate VARCHAR(20) PRIMARY KEY,
                Model VARCHAR(255) DEFAULT 'Unknown',
                Year INT DEFAULT 2020,
                VIN VARCHAR(255) DEFAULT 'VIN-UNKNOWN',
                Next_Oil_Change DATE,
                Owner_id INT DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS appointment (
                Appointment_id INT AUTO_INCREMENT PRIMARY KEY,
                Date DATE NOT NULL,
                Time TIME NOT NULL,
                Notes TEXT,
                Car_plate VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS service (
                Service_ID INT AUTO_INCREMENT PRIMARY KEY,
                Service_Type VARCHAR(255) NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS appointment_service (
                Appointment_id INT,
                Service_ID INT,
                PRIMARY KEY (Appointment_id, Service_ID)
            )
            """
        ]
        
        for i, sql in enumerate(tables_sql, 1):
            cursor.execute(sql)
            print(f"✅ Table {i}/5 created or already exists")
        
        # Insert default services
        services = [
            (1, 'Oil Change'),
            (2, 'Tire Rotation'), 
            (3, 'Brake Inspection'),
            (4, 'Battery Check')
        ]
        
        for service_id, service_type in services:
            cursor.execute(
                "INSERT IGNORE INTO service (Service_ID, Service_Type) VALUES (%s, %s)",
                (service_id, service_type)
            )
        
        conn.commit()
        print("🎉 Database setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    setup_database()