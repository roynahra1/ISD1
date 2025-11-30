import os
import mysql.connector
from mysql.connector import Error
import logging

logger = logging.getLogger(__name__)

def get_db_config():
    """Get database configuration"""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "isd"),
        "auth_plugin": "mysql_native_password"
    }

def get_connection():
    """Get database connection with error handling"""
    try:
        config = get_db_config()
        logger.info(f"Connecting to database: {config['database']}")
        return mysql.connector.connect(**config)
    except Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def _safe_close(cursor=None, conn=None):
    """Safely close database connections"""
    try:
        if cursor:
            cursor.close()
    except Exception as e:
        logger.warning(f"Error closing cursor: {e}")
    try:
        if conn:
            conn.close()
    except Exception as e:
        logger.warning(f"Error closing connection: {e}")

def get_car_info(plate_number):
    """Get car information from database by license plate - USING YOUR ACTUAL SCHEMA"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Query using your ACTUAL table and column names from your SQL dump
        query = """
        SELECT 
            c.Car_plate,
            c.Model,
            c.Year,
            c.VIN,
            c.Next_Oil_Change,
            o.Owner_Name,
            o.Owner_Email,
            o.PhoneNUMB,
            sh.Mileage,
            sh.Last_Oil_Change,
            sh.Notes,
            sh.Service_Date
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        LEFT JOIN service_history sh ON c.Car_plate = sh.Car_plate
        WHERE c.Car_plate = %s
        ORDER BY sh.Service_Date DESC 
        LIMIT 1
        """
        
        cursor.execute(query, (plate_number.upper(),))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"✅ Found car info for plate: {plate_number}")
            
            # Format the response to match what your frontend expects
            formatted_result = {
                "plate_number": result["Car_plate"],
                "model": result["Model"] or "Unknown",
                "year": result["Year"] or "Unknown",
                "vin": result["VIN"] or "Unknown",
                "next_oil_change_due": result["Next_Oil_Change"],
                "owner_name": result["Owner_Name"] or "Unknown",
                "owner_email": result["Owner_Email"] or "Unknown", 
                "owner_phone": result["PhoneNUMB"] or "Unknown",
                "kms": result["Mileage"] or "0",
                "last_oil_change": result["Last_Oil_Change"],
                "notes": result["Notes"] or "No notes",
                "last_service_date": result["Service_Date"]
            }
            return formatted_result
        else:
            logger.info(f"❌ No car found for plate: {plate_number}")
            return None
            
    except Error as e:
        logger.error(f"Database error in get_car_info: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_car_info: {e}")
        return None
    finally:
        _safe_close(cursor, conn)

def update_car_maintenance(plate, kms, notes):
    """Update car maintenance information - USING YOUR ACTUAL SCHEMA"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert into service_history table (your actual schema)
        insert_query = """
        INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
        VALUES (CURDATE(), %s, CURDATE(), %s, %s)
        """
        
        cursor.execute(insert_query, (kms, notes, plate.upper()))
        conn.commit()
        logger.info(f"✅ Updated car maintenance in service_history: {plate}")
        return True
            
    except Error as e:
        logger.error(f"Database error in update_car_maintenance: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error in update_car_maintenance: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        _safe_close(cursor, conn)

def get_all_cars():
    """Get all cars from database"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            c.Car_plate,
            c.Model,
            c.Year, 
            c.VIN,
            c.Next_Oil_Change,
            o.Owner_Name,
            o.Owner_Email
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        ORDER BY c.Car_plate
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        return results
            
    except Error as e:
        logger.error(f"Database error in get_all_cars: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_all_cars: {e}")
        return []
    finally:
        _safe_close(cursor, conn)

def get_service_history(plate_number):
    """Get service history for a car"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            Service_Date,
            Mileage,
            Last_Oil_Change, 
            Notes
        FROM service_history 
        WHERE Car_plate = %s
        ORDER BY Service_Date DESC
        """
        
        cursor.execute(query, (plate_number.upper(),))
        results = cursor.fetchall()
        return results
            
    except Error as e:
        logger.error(f"Database error in get_service_history: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_service_history: {e}")
        return []
    finally:
        _safe_close(cursor, conn)