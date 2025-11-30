# after_service.py
from flask import Blueprint, request, jsonify, render_template
import mysql.connector
from mysql.connector import Error
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

after_service_bp = Blueprint('after_service', __name__)

def get_db_config():
    """Get database configuration with test environment support"""
    if os.getenv('TESTING'):
        # Use test database for tests
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("TEST_DB_NAME", "isd_test"),
            "auth_plugin": "mysql_native_password"
        }
    else:
        # Use production database
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

# ==================== ROUTES ====================

@after_service_bp.route('/after-service')
def after_service_form():
    """Serve the after-service form"""
    return render_template('after_service_form.html')

@after_service_bp.route('/api/car/<car_plate>')
def get_car_info(car_plate):
    """Get car information by plate number"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            c.Car_plate,
            c.Model,
            c.Year,
            c.VIN,
            c.Next_Oil_Change,
            o.Owner_Name,
            o.Owner_Email,
            o.PhoneNUMB
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        WHERE c.Car_plate = %s
        """
        cursor.execute(query, (car_plate,))
        car_data = cursor.fetchone()
        
        if car_data:
            return jsonify({
                "status": "success", 
                "data": car_data
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Car not found"
            }), 404
            
    except Error as e:
        logger.error(f"Database error in get_car_info: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Server error in get_car_info: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, connection)

@after_service_bp.route('/api/update-car-service', methods=['POST'])
def update_car_service():
    """Handle after-service form submission - creates new service history records"""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        
        # Extract form data
        car_plate = data.get('car_plate')
        model = data.get('model')
        year = data.get('year')
        vin = data.get('vin')
        service_date = data.get('service_date')
        mileage = data.get('mileage')
        last_oil_change = data.get('last_oil_change')
        next_oil_change = data.get('next_oil_change')
        notes = data.get('notes')
        services_performed = data.get('services_performed', [])
        
        # Validate required fields
        if not car_plate:
            return jsonify({"status": "error", "message": "Car plate is required"}), 400
        
        connection = get_connection()
        cursor = connection.cursor()

        # Start transaction
        connection.start_transaction()
        
        try:
            # 1. Handle car information
            upsert_car_query = """
            INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_ID)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                Model = VALUES(Model),
                Year = VALUES(Year), 
                VIN = VALUES(VIN),
                Next_Oil_Change = VALUES(Next_Oil_Change)
            """
            cursor.execute(upsert_car_query, (
                car_plate, model, year, vin, next_oil_change, 1
            ))
            
            # 2. Create NEW service history record
            insert_history_query = """
            INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_history_query, (
                service_date, 
                mileage if mileage else None, 
                last_oil_change if last_oil_change else None, 
                notes if notes else None, 
                car_plate
            ))
            
            # Get the auto-generated History_ID
            history_id = cursor.lastrowid
            
            # 3. Link services performed
            if services_performed:
                insert_service_query = """
                INSERT IGNORE INTO service_history_service (History_ID, Service_ID)
                VALUES (%s, %s)
                """
                for service_id in services_performed:
                    cursor.execute(insert_service_query, (history_id, service_id))
            
            # Commit transaction
            connection.commit()
            
            logger.info(f"Successfully updated car {car_plate} and created service record #{history_id}")
            
            return jsonify({
                "status": "success", 
                "message": f"Car information updated and service logged successfully!",
                "history_id": history_id,
                "service_date": service_date
            })
            
        except Error as e:
            # Rollback on error
            connection.rollback()
            logger.error(f"Database error in update_car_service transaction: {e}")
            
            # Handle specific MySQL errors
            if "1062" in str(e) and "PRIMARY" in str(e):
                return jsonify({
                    "status": "error", 
                    "message": "Service record conflict. Please try again."
                }), 500
            else:
                return jsonify({
                    "status": "error", 
                    "message": f"Database error: {str(e)}"
                }), 500
            
    except Exception as e:
        logger.error(f"Server error in update_car_service: {e}")
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500
    finally:
        _safe_close(cursor, connection)

# ==================== ADDITIONAL FUNCTIONALITIES ====================

@after_service_bp.route('/api/service-history/<car_plate>')
def get_service_history(car_plate):
    """Get complete service history for a car"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            sh.History_ID,
            sh.Service_Date,
            sh.Mileage,
            sh.Last_Oil_Change,
            sh.Notes,
            GROUP_CONCAT(s.Service_Type SEPARATOR ', ') as Services_Performed
        FROM service_history sh
        LEFT JOIN service_history_service shs ON sh.History_ID = shs.History_ID
        LEFT JOIN service s ON shs.Service_ID = s.Service_ID
        WHERE sh.Car_plate = %s
        GROUP BY sh.History_ID
        ORDER BY sh.Service_Date DESC
        """
        cursor.execute(query, (car_plate,))
        service_history = cursor.fetchall()
        
        return jsonify({
            "status": "success", 
            "data": service_history,
            "count": len(service_history)
        })
            
    except Error as e:
        logger.error(f"Database error in get_service_history: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, connection)

@after_service_bp.route('/api/all-cars')
def get_all_cars():
    """Get all cars in the system"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
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
            (SELECT MAX(Service_Date) FROM service_history WHERE Car_plate = c.Car_plate) as Last_Service_Date
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        ORDER BY c.Car_plate
        """
        cursor.execute(query)
        cars = cursor.fetchall()
        
        return jsonify({
            "status": "success", 
            "data": cars,
            "count": len(cars)
        })
            
    except Error as e:
        logger.error(f"Database error in get_all_cars: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, connection)

@after_service_bp.route('/api/upcoming-services')
def get_upcoming_services():
    """Get cars with upcoming service needs"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            c.Car_plate,
            c.Model,
            c.Next_Oil_Change,
            o.Owner_Name,
            o.PhoneNUMB,
            DATEDIFF(c.Next_Oil_Change, CURDATE()) as Days_Until_Service
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        WHERE c.Next_Oil_Change IS NOT NULL 
        AND c.Next_Oil_Change <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
        ORDER BY c.Next_Oil_Change ASC
        """
        cursor.execute(query)
        upcoming_services = cursor.fetchall()
        
        return jsonify({
            "status": "success", 
            "data": upcoming_services,
            "count": len(upcoming_services)
        })
            
    except Error as e:
        logger.error(f"Database error in get_upcoming_services: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, connection)

@after_service_bp.route('/api/dashboard-stats')
def get_dashboard_stats():
    """Get dashboard statistics"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Total cars
        cursor.execute("SELECT COUNT(*) as total_cars FROM car")
        total_cars = cursor.fetchone()['total_cars']
        
        # Total services this month
        cursor.execute("""
            SELECT COUNT(*) as services_this_month 
            FROM service_history 
            WHERE MONTH(Service_Date) = MONTH(CURDATE()) 
            AND YEAR(Service_Date) = YEAR(CURDATE())
        """)
        services_this_month = cursor.fetchone()['services_this_month']
        
        # Upcoming services
        cursor.execute("""
            SELECT COUNT(*) as upcoming_services 
            FROM car 
            WHERE Next_Oil_Change IS NOT NULL 
            AND Next_Oil_Change <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """)
        upcoming_services = cursor.fetchone()['upcoming_services']
        
        # Recent services
        cursor.execute("""
            SELECT COUNT(*) as recent_services 
            FROM service_history 
            WHERE Service_Date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """)
        recent_services = cursor.fetchone()['recent_services']
        
        return jsonify({
            "status": "success", 
            "data": {
                "total_cars": total_cars,
                "services_this_month": services_this_month,
                "upcoming_services": upcoming_services,
                "recent_services": recent_services
            }
        })
            
    except Error as e:
        logger.error(f"Database error in get_dashboard_stats: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, connection)

# Health check endpoint
@after_service_bp.route('/api/health')
def health_check():
    """Health check for after-service routes"""
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        _safe_close(cursor, connection)
        
        return jsonify({
            "status": "success",
            "message": "After-service routes are healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Database connection failed",
            "database": "disconnected",
            "timestamp": datetime.now().isoformat()
        }), 500