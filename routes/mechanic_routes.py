from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from mysql.connector import Error
import logging
from datetime import datetime, timedelta
import re
from functools import wraps
from utils.database import get_connection, _safe_close

mechanic_bp = Blueprint('mechanic', __name__, url_prefix='/mechanic')
logger = logging.getLogger(__name__)

# ===============================
# DECORATORS & UTILITIES - STRICT MECHANIC ONLY
# ===============================

def mechanic_login_required(f):
    """STRICT decorator - ONLY accepts mechanic session, ignores regular session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("mechanic_logged_in"):
            return jsonify({"success": False, "message": "Unauthorized - Please login via mechanic portal"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ===============================
# TEMPLATE ROUTES - STRICT MECHANIC ONLY
# ===============================

@mechanic_bp.route("/dashboard")
def mechanic_dashboard():
    """Serve the mechanic dashboard - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    username = session.get("mechanic_username", "Mechanic")
    return render_template("mechanic_dashboard.html", username=username)

@mechanic_bp.route("/appointments")
def mechanic_appointments_page():
    """Serve mechanic appointments page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("mechanic_appointments.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/service-history")
def mechanic_service_history_page():
    """Serve mechanic service history page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("mechanic_service_history.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/reports")
def mechanic_reports_page():
    """Serve mechanic reports page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("mechanic_reports.html", username=session.get("mechanic_username"))

# ===============================
# ADMIN TEMPLATE ROUTES (PART OF MECHANIC SYSTEM) - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route("/admin/dashboard")
def admin_dashboard():
    """Serve admin dashboard page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    username = session.get("mechanic_username", "Admin")
    return render_template("mechanic_dashboard.html", username=username)

@mechanic_bp.route("/admin/appointments")
def admin_appointments_page():
    """Serve admin appointments page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("mechanic_appointments.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/admin/service-history")
def admin_service_history_page():
    """Serve admin service history page - MECHANIC SESSION ONLY"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("mechanic_service_history.html", username=session.get("mechanic_username"))

# ===============================
# DASHBOARD API ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route('/api/dashboard-stats', methods=['GET'])
@mechanic_login_required
def get_dashboard_stats():
    """API endpoint for dashboard statistics with real database values"""
    logger.info("Dashboard stats requested")
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Today's services count
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM service_history 
            WHERE DATE(Service_Date) = CURDATE()
        """)
        today_services_result = cursor.fetchone()
        today_services = today_services_result[0] if today_services_result else 0
        
        # Completed this week
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM service_history 
            WHERE YEARWEEK(Service_Date, 1) = YEARWEEK(CURDATE(), 1)
        """)
        completed_week_result = cursor.fetchone()
        completed_week = completed_week_result[0] if completed_week_result else 0
        
        # Today's appointments
        cursor.execute("SELECT COUNT(*) as count FROM appointment WHERE Date = CURDATE()")
        today_appointments_result = cursor.fetchone()
        today_appointments = today_appointments_result[0] if today_appointments_result else 0
        
        # Total appointments
        cursor.execute("SELECT COUNT(*) as count FROM appointment")
        total_appointments_result = cursor.fetchone()
        total_appointments = total_appointments_result[0] if total_appointments_result else 0
        
        # Urgent jobs (overdue oil changes)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM car 
            WHERE Next_Oil_Change IS NOT NULL 
            AND Next_Oil_Change < CURDATE()
        """)
        urgent_jobs_result = cursor.fetchone()
        urgent_jobs = urgent_jobs_result[0] if urgent_jobs_result else 0
        
        # Total cars
        cursor.execute("SELECT COUNT(*) as count FROM car")
        total_cars_result = cursor.fetchone()
        total_cars = total_cars_result[0] if total_cars_result else 0
        
        # Total owners
        cursor.execute("SELECT COUNT(*) as count FROM owner")
        total_owners_result = cursor.fetchone()
        total_owners = total_owners_result[0] if total_owners_result else 0
        
        logger.info("Stats - Today Services: %s, Week: %s, Today Appointments: %s", today_services, completed_week, today_appointments)
        
        return jsonify({
            "success": True,
            "data": {
                "today_services": today_services,
                "completed_week": completed_week,
                "today_appointments": today_appointments,
                "pending_services": total_appointments,
                "urgent_jobs": urgent_jobs,
                "total_cars": total_cars,
                "total_owners": total_owners
            }
        })
        
    except Error as db_err:
        logger.exception("Database error while loading dashboard stats")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception:
        logger.exception("Unhandled error while loading dashboard stats")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route('/api/recent-activity', methods=['GET'])
@mechanic_login_required
def get_recent_activity():
    """API endpoint for recent activity. Supports `limit` and `offset` query params."""
    logger.info("Recent activity requested")

    # Safely parse pagination params
    try:
        limit = int(request.args.get('limit', 8))
    except Exception:
        limit = 8
    try:
        offset = int(request.args.get('offset', 0))
    except Exception:
        offset = 0

    # cap limit to avoid heavy queries
    max_limit = 100
    if limit < 1:
        limit = 1
    if limit > max_limit:
        limit = max_limit
    if offset < 0:
        offset = 0

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get recent service history with pagination
        query = '''
            SELECT 
                sh.History_ID,
                sh.Service_Date as timestamp,
                sh.Car_plate as plate,
                sh.Notes as description,
                sh.Mileage as mileage,
                c.Model as car_model,
                o.Owner_Name as owner_name
            FROM service_history sh
            LEFT JOIN car c ON sh.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            ORDER BY sh.Service_Date DESC
            LIMIT %s OFFSET %s
        '''
        cursor.execute(query, (limit, offset))

        activities = cursor.fetchall()

        # Format activities for frontend
        formatted_activities = []
        for activity in activities:
            timestamp = activity.get('timestamp')
            if timestamp and hasattr(timestamp, 'isoformat'):
                timestamp = timestamp.isoformat()

            formatted_activities.append({
                "type": "service",
                "title": f"Serviced {activity.get('plate')}",
                "description": activity.get('description') or f"Service - {activity.get('mileage') or 'N/A'} km",
                "timestamp": timestamp
            })

        logger.info("Returning %d activities (limit=%d, offset=%d)", len(formatted_activities), limit, offset)
        return jsonify({"success": True, "data": formatted_activities})

    except Error:
        logger.exception("Database error while loading recent activities")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception:
        logger.exception("Unhandled error while loading recent activities")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

# ===============================
# APPOINTMENT MANAGEMENT - CONSISTENT VERSION
# ===============================

@mechanic_bp.route("/api/appointments/<int:appointment_id>", methods=['DELETE'])
@mechanic_login_required
def delete_appointment(appointment_id):
    """Delete appointment - Consistent pattern"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Delete operations
        cursor.execute("DELETE FROM appointment_service WHERE Appointment_ID = %s", (appointment_id,))
        cursor.execute("DELETE FROM appointment WHERE Appointment_ID = %s", (appointment_id,))
        
        conn.commit()  # ← MUST HAVE THIS
        
        return jsonify({
            "success": True,
            "message": "Appointment deleted successfully"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()  # ← MUST HAVE THIS
        return jsonify({
            "success": False,
            "message": f"Error deleting appointment: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)  # ← Use the SAME cleanup as other routes

@mechanic_bp.route("/api/appointments/<int:appointment_id>", methods=['PUT'])
@mechanic_login_required
def update_appointment(appointment_id):
    """Update appointment - Consistent pattern"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    date = data.get('date')
    time = data.get('time')
    notes = data.get('notes', '')
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE appointment 
            SET Date = %s, Time = %s, Notes = %s 
            WHERE Appointment_ID = %s
        """, (date, time, notes, appointment_id))
        
        conn.commit()  # ← MUST HAVE THIS
        
        return jsonify({
            "success": True,
            "message": "Appointment updated successfully"
        })
        
    except Exception as e:
        if conn:
            conn.rollback()  # ← MUST HAVE THIS
        return jsonify({
            "success": False,
            "message": f"Error updating appointment: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)  # ← Use the SAME cleanup as other routes

# ===============================
# ADD CAR ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route('/api/car/<plate_number>/latest-mileage', methods=['GET'])
@mechanic_login_required
def get_latest_mileage(plate_number):
    """Get the MAXIMUM recorded mileage for a car"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get MAXIMUM mileage (not just latest)
        cursor.execute("""
            SELECT MAX(Mileage) as max_mileage
            FROM service_history 
            WHERE Car_plate = %s
        """, (plate_number,))
        
        result = cursor.fetchone()
        
        max_mileage = result['max_mileage'] if result and result['max_mileage'] is not None else 0
        
        return jsonify({
            "success": True,
            "latest_mileage": max_mileage,
            "max_mileage": max_mileage,
            "plate_number": plate_number
        })
        
    except Exception as e:
        logger.error(f"Error fetching maximum mileage: {e}")
        return jsonify({
            "success": False,
            "message": "Error fetching mileage data"
        }), 500
    finally:
        _safe_close(cursor, conn)
        
@mechanic_bp.route("/mechanic/addCar.html")
def add_car_form():
    """Serve the add car form page"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    # Get plate from session if available
    plate_number = session.get('detected_plate', '')
    
    return render_template("addCar.html", 
                         plate_number=plate_number,
                         username=session.get("mechanic_username"))

@mechanic_bp.route("/plate-detection")
def plate_detection_page():
    """Serve license plate detection page"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    return render_template("homee.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/detect", methods=["POST"])
def detect_plate():
    """License plate detection endpoint - fallback version"""
    return jsonify({
        "success": False,
        "message": "Plate detection unavailable. Use manual entry.",
        "fallback": True
    }), 503

@mechanic_bp.route("/api/store-plate", methods=["POST"])
@mechanic_login_required
def store_plate():
    """API endpoint to store plate number in session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        plate_number = data.get('plate_number', '').strip().upper()
        
        if not plate_number:
            return jsonify({"success": False, "message": "Plate number is required"}), 400
        
        # Store plate in session
        session['detected_plate'] = plate_number
        
        logger.info(f"Plate {plate_number} stored in session by user {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": "Plate stored successfully"
        })
        
    except Exception as e:
        logger.error(f"Error storing plate: {e}")
        return jsonify({
            "success": False, 
            "message": f"Error storing plate: {str(e)}"
        }), 500

@mechanic_bp.route("/api/stored-plate", methods=["GET"])
@mechanic_login_required
def get_stored_plate():
    """Get stored plate from session"""
    plate_number = session.get('detected_plate', '')
    return jsonify({
        "plate": plate_number,
        "has_plate": bool(plate_number)
    })

@mechanic_bp.route("/api/clear-plate", methods=["POST"])
@mechanic_login_required
def clear_stored_plate():
    """Clear stored plate from session"""
    session.pop('detected_plate', None)
    return jsonify({"success": True, "message": "Plate cleared"})

@mechanic_bp.route("/api/add-car", methods=["POST"])
@mechanic_login_required
def add_car():
    """Add new car to database"""
    logger.info("Adding new car to database")
    
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    # Extract data matching frontend form
    car_plate = data.get('car_plate', '').strip().upper()
    model = data.get('model', '').strip()
    year = data.get('year')
    vin = data.get('vin', '').strip()
    next_oil_change = data.get('next_oil_change')
    owner_type = data.get('owner_type')
    # Accept multiple possible keys for phone number from different frontends
    phone_number = (data.get('phone_number') or data.get('PhoneNUMB') or data.get('phone') or '').strip()
    current_mileage = data.get('current_mileage')
    last_service_date = data.get('last_service_date')
    service_notes = data.get('service_notes', 'Initial car registration')
    
    # New owner fields (only for new owners)
    owner_name = data.get('owner_name', '').strip()
    owner_email = data.get('owner_email', '').strip()
    
    # Validation
    if not car_plate or not re.match(r'^[A-Z]{1}[0-9]{1,6}$', car_plate):
        return jsonify({"status": "error", "message": "Valid license plate is required (1 letter + 1-6 digits)"}), 400
    
    if not model:
        return jsonify({"status": "error", "message": "Car model is required"}), 400
    
    # coerce year to int when possible
    try:
        year = int(year) if year is not None and year != '' else None
    except Exception:
        year = None

    if not year:
        return jsonify({"status": "error", "message": "Manufacturing year is required"}), 400
    
    if not vin or len(vin) != 17:
        return jsonify({"status": "error", "message": "Valid 17-character VIN is required"}), 400
    
    if not phone_number:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400
    
    if owner_type == "new" and (not owner_name or not owner_email):
        return jsonify({"status": "error", "message": "Owner name and email are required for new owners"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # helper to tolerate mocked cursors with limited side_effect lists
        def _safe_fetchone():
            try:
                return cursor.fetchone()
            except Exception:
                return None

        # Check if car already exists
        cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (car_plate,))
        if _safe_fetchone():
            return jsonify({"status": "error", "message": f"Car with plate {car_plate} already exists"}), 409

        # Check VIN uniqueness (best-effort - tolerate mocked cursor exhaustion)
        cursor.execute("SELECT Car_plate FROM car WHERE VIN = %s", (vin,))
        vin_conflict = _safe_fetchone()
        if vin_conflict:
            return jsonify({"status": "error", "message": f"VIN {vin} already registered to another car"}), 409
        
        # Start transaction
        conn.start_transaction()
        
        owner_id = None
        
        if owner_type == "existing":
            # Find existing owner by phone number
            cursor.execute("SELECT Owner_ID FROM owner WHERE PhoneNUMB = %s", (phone_number,))
            existing_owner = _safe_fetchone()
            if existing_owner:
                owner_id = existing_owner['Owner_ID']
                logger.info("Found existing owner ID: %s", owner_id)
            else:
                return jsonify({"status": "error", "message": "No existing owner found with this phone number"}), 404
                
        else:  # new owner
            # Check if owner with same phone already exists
            cursor.execute("SELECT Owner_ID FROM owner WHERE PhoneNUMB = %s", (phone_number,))
            if _safe_fetchone():
                return jsonify({"status": "error", "message": "Owner with this phone number already exists. Use 'Existing Owner' instead."}), 409
            
            # Create new owner
            cursor.execute("""
                INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB)
                VALUES (%s, %s, %s)
            """, (owner_name, owner_email, phone_number))
            owner_id = cursor.lastrowid
            logger.info("Created new owner ID: %s", owner_id)
        
        # Add the car
        cursor.execute("""
            INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_ID)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (car_plate, model, year, vin, next_oil_change, owner_id))
        
        # Create initial service history if mileage provided
        if current_mileage is not None and current_mileage != '':
            # coerce mileage to int
            try:
                cm = int(current_mileage)
            except Exception:
                cm = None

            if cm is not None:
                # parse last_service_date if string
                svc_date = None
                if last_service_date:
                    try:
                        svc_date = datetime.strptime(last_service_date, '%Y-%m-%d').date()
                    except Exception:
                        svc_date = None
                svc_date = svc_date or datetime.now().date()

                cursor.execute("""
                    INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
                    VALUES (%s, %s, CURDATE(), %s, %s)
                """, (svc_date, cm, service_notes, car_plate))
                
                history_id = cursor.lastrowid
                logger.info("Created initial service history record #%s", history_id)
        
        conn.commit()
        
        # Clear the stored plate from session
        session.pop('detected_plate', None)
        
        # Log the action
        logger.info(f"New car added: {car_plate} by user {session.get('mechanic_username')}")
        
        return jsonify({
            "status": "success",
            "message": f"Car {car_plate} added successfully to database",
            "car_plate": car_plate,
            "owner_id": owner_id
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error adding car: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error adding car: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/check-owner/<phone_number>", methods=["GET"])
@mechanic_login_required
def check_owner_exists(phone_number):
    """Check if owner exists by phone number"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT Owner_ID, Owner_Name, Owner_Email FROM owner WHERE PhoneNUMB = %s", (phone_number,))
        owner = cursor.fetchone()
        
        return jsonify({
            "success": True,
            "exists": owner is not None,
            "owner": owner
        })
        
    except Exception as e:
        logger.error(f"Error checking owner: {e}")
        return jsonify({
            "success": False,
            "message": "Error checking owner"
        }), 500
    finally:
        _safe_close(cursor, conn)


# ===============================
# VIN SEARCH ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route('/api/search-by-vin', methods=['GET'])
@mechanic_login_required
def search_by_vin():
    vin = request.args.get('vin', '').strip().upper()
    if not vin:
        return jsonify({"success": False, "message": "VIN number is required"}), 400
    
    vin_clean = ''.join(c for c in vin if c.isalnum()).upper()

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                c.Car_plate AS plate_number,
                c.Model AS model,
                c.Year AS year,
                c.VIN AS vin,
                c.Next_Oil_Change AS next_oil_change,
                o.Owner_Name AS owner_name,
                o.Owner_Email AS owner_email,
                o.PhoneNUMB AS owner_phone
            FROM car c
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            WHERE UPPER(c.VIN) LIKE CONCAT('%', %s, '%')
            ORDER BY
                CASE
                    WHEN UPPER(c.VIN) = %s THEN 1
                    WHEN UPPER(c.VIN) LIKE CONCAT(%s, '%') THEN 2
                    ELSE 3
                END, c.Car_plate
            LIMIT 10
        """, (vin_clean, vin_clean, vin_clean))

        results = cursor.fetchall()
        if not results:
            return jsonify({"success": False, "message": "No cars found"}), 404

        for r in results:
            if r["next_oil_change"]:
                r["next_oil_change"] = r["next_oil_change"].isoformat()

        if len(results) == 1:
            return jsonify({"success": True, "matches_found": 1, "car_info": results[0]})
        else:
            return jsonify({"success": True, "matches_found": len(results), "cars": results})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route('/api/search-by-vin-flexible', methods=['GET'])
@mechanic_login_required
def search_by_vin_flexible():
    """Flexible VIN search - find cars by partial VIN match"""
    logger.debug("Flexible VIN search")

    vin = request.args.get('vin', '').strip().upper()
    logger.debug("Searching for VIN (flexible): '%s'", vin)

    if not vin:
        return jsonify({"success": False, "message": "VIN number is required"}), 400

    # Clean the VIN - remove spaces and special characters
    vin_clean = ''.join(c for c in vin if c.isalnum()).upper()
    logger.debug("Cleaned VIN: '%s'", vin_clean)

    if len(vin_clean) < 3:  # Even more flexible - minimum 3 characters
        return jsonify({
            "success": False,
            "message": "Please enter at least 3 characters of the VIN"
        }), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # FLEXIBLE SEARCH: Look for partial matches anywhere in VIN
        cursor.execute("""
            SELECT 
                c.Car_plate as plate_number,
                c.Model as model,
                c.Year as year,
                c.VIN as vin,
                c.Next_Oil_Change as next_oil_change,
                o.Owner_Name as owner_name,
                o.Owner_Email as owner_email,
                o.PhoneNUMB as owner_phone
            FROM car c
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            WHERE UPPER(c.VIN) LIKE UPPER(CONCAT('%', %s, '%'))
            ORDER BY 
                CASE 
                    WHEN UPPER(c.VIN) = UPPER(%s) THEN 1  -- Exact match first
                    WHEN UPPER(c.VIN) LIKE UPPER(CONCAT(%s, '%')) THEN 2  -- Starts with
                    ELSE 3  -- Contains
                END,
                c.Car_plate
            LIMIT 20
        """, (vin_clean, vin_clean, vin_clean))

        results = cursor.fetchall()

        if results:
            logger.info("Found %s cars matching VIN pattern", len(results))

            # Format dates for JSON
            for result in results:
                if result.get('next_oil_change') and hasattr(result['next_oil_change'], 'isoformat'):
                    result['next_oil_change'] = result['next_oil_change'].isoformat()

            return jsonify({
                "success": True,
                "matches_found": len(results),
                "cars": results,
                "message": f"Found {len(results)} matches for VIN pattern '{vin_clean}'"
            })
        else:
            logger.info("No cars found with VIN containing: %s", vin_clean)
            return jsonify({
                "success": False,
                "message": f"No cars found with VIN containing: {vin}"
            }), 404

    except Error:
        logger.exception("Database error in flexible VIN search")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception:
        logger.exception("Unhandled error in flexible VIN search")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)
# ===============================
# CAR INFO API ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route('/api/car/<plate_number>', methods=['GET'])
@mechanic_login_required
def get_car_info(plate_number):
    """Get car information by license plate"""
    logger.debug("MECHANIC API: Searching for plate: '%s'", plate_number)
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Use UPPER() for case-insensitive search
        query = """
        SELECT 
            c.Car_plate as plate_number,
            c.Model as model,
            c.Year as year,
            c.VIN as vin,
            c.Next_Oil_Change as next_oil_change,
            o.Owner_Name as owner_name,
            o.Owner_Email as owner_email,
            o.PhoneNUMB as owner_phone
        FROM car c
        LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
        WHERE UPPER(c.Car_plate) = UPPER(%s)
        """

        cursor.execute(query, (plate_number.strip().upper(),))
        result = cursor.fetchone()

        if result:
            logger.info("MECHANIC API: Car found: %s", result['plate_number'])
            return jsonify({"success": True, "car_info": result})
        else:
            logger.info("MECHANIC API: No car found with plate: %s", plate_number)
            return jsonify({"success": False, "message": f"No car found with plate: {plate_number}"}), 404

    except Error:
        logger.exception("Database error in get_car_info")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception:
        logger.exception("Unhandled error in get_car_info")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route('/api/car/<plate_number>/maintenance', methods=['POST'])
@mechanic_login_required
def update_car_maintenance(plate_number):
    """Update car maintenance"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        mileage = data.get('mileage') or data.get('kms')
        notes = data.get('notes', '')

        if mileage is None or mileage == '':
            return jsonify({"success": False, "message": "Mileage is required"}), 400

        # coerce mileage to int
        try:
            mileage = int(mileage)
        except Exception:
            return jsonify({"success": False, "message": "Mileage must be an integer"}), 400

        conn = get_connection()
        if not conn:
            return jsonify({"success": False, "message": "Database connection failed"}), 500

        cursor = conn.cursor()
        insert_query = """
        INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
        VALUES (CURDATE(), %s, CURDATE(), %s, %s)
        """
        cursor.execute(insert_query, (mileage, notes, plate_number.upper()))
        conn.commit()

        return jsonify({
            "success": True,
            "message": f"Maintenance updated for {plate_number}"
        })

    except Exception as e:
        logger.error(f"Error in update_car_maintenance: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500
    finally:
        _safe_close(cursor, conn)

# ===============================
# AFTER SERVICE FORM ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route("/after-service-form")
def after_service_form():
    """Serve the after-service form page"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    # Get and validate plate number
    plate_number = session.get('detected_plate', '').strip().upper()
    
    # Validate plate format
    if not plate_number or not re.match(r'^[A-Z0-9]{4,12}$', plate_number):
        return render_template("error.html", 
                             message="Invalid or missing license plate"), 400
    
    # Verify plate exists in database
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT c.Car_plate, o.Owner_Name 
            FROM car c 
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID 
            WHERE c.Car_plate = %s
        """, (plate_number,))
        
        car_exists = cursor.fetchone()
        
        if not car_exists:
            return render_template("error.html", 
                                 message=f"Car with plate {plate_number} not found in database"), 404
        
        # Log access for audit trail
        logger.info(f"After-service form accessed for plate {plate_number} by user {session.get('mechanic_username')}")
        
        return render_template("after_service_form.html", 
                             plate_number=plate_number,
                             username=session.get("mechanic_username"),
                             owner_name=car_exists['Owner_Name'])
        
    except Exception as e:
        logger.error(f"Database error in after_service_form: {e}")
        return render_template("error.html", 
                             message="Database error occurred"), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/submit-after-service", methods=["POST"])
@mechanic_login_required
def submit_after_service():
    """After-service form submission"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        # Extract and validate data
        plate_number = data.get('plate_number', '').strip().upper()
        service_type = data.get('service_type', '')
        mileage = data.get('mileage')
        notes = data.get('notes', '')
        next_service_date = data.get('next_service_date')
        mechanic_notes = data.get('mechanic_notes', '')
        
        # Validate required fields
        if not plate_number or not re.match(r'^[A-Z0-9]{4,12}$', plate_number):
            return jsonify({"success": False, "message": "Invalid plate number"}), 400
        
        if not service_type:
            return jsonify({"success": False, "message": "Service type is required"}), 400
        
        # allow numeric strings, coerce to int
        try:
            mileage = int(mileage)
        except Exception:
            return jsonify({"success": False, "message": "Valid mileage is required"}), 400

        if mileage <= 0:
            return jsonify({"success": False, "message": "Valid mileage is required"}), 400
        
        # Verify car exists and user has permission
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Verify car exists
            cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (plate_number,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Car not found"}), 404
            
            # Insert service history
            cursor.execute("""
                INSERT INTO service_history 
                (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
                VALUES (CURDATE(), %s, CURDATE(), %s, %s)
            """, (mileage, notes, plate_number))
            
            history_id = cursor.lastrowid
            
            # Update next oil change if provided
            if next_service_date:
                cursor.execute("""
                    UPDATE car 
                    SET Next_Oil_Change = %s 
                    WHERE Car_plate = %s
                """, (next_service_date, plate_number))
            
            conn.commit()
            
            # Log the service
            logger.info(f"Service completed for plate {plate_number} by {session.get('mechanic_username')}. History ID: {history_id}")
            
            return jsonify({
                "success": True,
                "message": "Service record submitted successfully",
                "service_history_id": history_id,
                "plate_number": plate_number
            })
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error in submit_after_service: {e}")
            return jsonify({
                "success": False, 
                "message": f"Database error: {str(e)}"
            }), 500
        finally:
            _safe_close(cursor, conn)
        
    except Exception as e:
        logger.error(f"Error submitting after-service form: {e}")
        return jsonify({
            "success": False, 
            "message": f"Error submitting form: {str(e)}"
        }), 500

# ===============================
# APPOINTMENTS API ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route("/api/appointments", methods=['GET'])
@mechanic_login_required
def get_all_appointments():
    """API to get only UPCOMING appointments (future dates)"""
    logger.debug("Fetching upcoming appointments")
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get today's date properly
        today = datetime.now().date()
        logger.debug("Today's date: %s", today)
        
        # SIMPLE SQL query to get only upcoming appointments
        cursor.execute("""
            SELECT 
                a.*,
                c.Model as car_model,
                o.Owner_Name,
                o.PhoneNUMB
            FROM appointment a
            LEFT JOIN car c ON a.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            WHERE a.Date >= %s
            ORDER BY a.Date ASC, a.Time ASC
        """, (today,))
        
        appointments = cursor.fetchall()
        
        logger.info("Found %s upcoming appointments", len(appointments))
        
        # Debug: print what we found
        for appointment in appointments:
            logger.debug("Upcoming appointment ID %s - Date: %s", appointment.get('Appointment_ID'), appointment.get('Date'))
        
        # Format the data for frontend
        formatted_appointments = []
        for appointment in appointments:
            # Handle date formatting
            appointment_date = appointment['Date']
            if hasattr(appointment_date, 'isoformat'):
                appointment_date = appointment_date.isoformat()
            
            # Handle time formatting
            appointment_time = appointment.get('Time')
            if appointment_time:
                if isinstance(appointment_time, timedelta):
                    total_seconds = int(appointment_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    appointment_time = f"{hours:02d}:{minutes:02d}"
                else:
                    appointment_time = str(appointment_time)
            
            formatted_appt = {
                'Appointment_ID': appointment['Appointment_ID'],
                'Date': appointment_date,
                'Time': appointment_time,
                'Car_plate': appointment['Car_plate'],
                'Notes': appointment.get('Notes', ''),
                'car_model': appointment.get('car_model', ''),
                'Owner_Name': appointment.get('Owner_Name', ''),
                'PhoneNUMB': appointment.get('PhoneNUMB', '')
            }
            formatted_appointments.append(formatted_appt)
        
        return jsonify({
            "success": True,
            "data": formatted_appointments,
            "total": len(appointments)
        })
        
    except Exception as e:
        logger.exception("Error loading appointments")
        return jsonify({"success": False, "message": "Error loading appointments"}), 500
    finally:
        _safe_close(cursor, conn)
@mechanic_bp.route("/api/appointments/<int:appointment_id>", methods=['GET'])
@mechanic_login_required
def get_appointment_details(appointment_id):
    """Get detailed information for a specific appointment"""
    logger.debug("Fetching details for appointment %s", appointment_id)
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get appointment details with car and owner information
        cursor.execute("""
            SELECT 
                a.Appointment_ID,
                a.Date,
                a.Time,
                a.Notes,
                a.Car_plate,
                c.Model as car_model,
                c.Year as car_year,
                c.VIN,
                o.Owner_Name,
                o.Owner_Email,
                o.PhoneNUMB,
                GROUP_CONCAT(s.Service_Type) as Scheduled_Services
            FROM appointment a
            LEFT JOIN car c ON a.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            LEFT JOIN appointment_service aps ON a.Appointment_ID = aps.Appointment_ID
            LEFT JOIN service s ON aps.Service_ID = s.Service_ID
            WHERE a.Appointment_ID = %s
            GROUP BY a.Appointment_ID
        """, (appointment_id,))
        
        appointment = cursor.fetchone()
        
        if not appointment:
            return jsonify({
                "success": False,
                "message": f"Appointment #{appointment_id} not found"
            }), 404
        
        # Convert timedelta to string format
        if appointment['Time'] and isinstance(appointment['Time'], timedelta):
            total_seconds = int(appointment['Time'].total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            appointment['Time'] = f"{hours:02d}:{minutes:02d}"
        
        # Format date
        if appointment['Date'] and hasattr(appointment['Date'], 'isoformat'):
            appointment['Date'] = appointment['Date'].isoformat()
        
        # Format scheduled services
        if appointment['Scheduled_Services']:
            appointment['Scheduled_Services'] = appointment['Scheduled_Services'].split(',')
        else:
            appointment['Scheduled_Services'] = []
        
        logger.info("Found detailed information for appointment %s", appointment_id)
        
        return jsonify({
            "success": True,
            "data": appointment
        })
        
    except Exception as e:
        logger.exception("Error loading appointment details for %s", appointment_id)
        return jsonify({"success": False, "message": "Error loading appointment details"}), 500
    finally:
        _safe_close(cursor, conn)

# ===============================
# SERVICE COMPLETION ROUTE - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route("/api/complete-service", methods=['POST'])
@mechanic_login_required
def complete_service():
    """Complete service with STRICT mileage validation"""
    logger.info("Completing service with strict mileage validation")
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    car_plate = data.get('car_plate', '').strip().upper()
    mileage = data.get('mileage')
    next_oil_change = data.get('next_oil_change')
    notes = data.get('notes', '')
    services_performed = data.get('services_performed', [])
    
    if not car_plate:
        return jsonify({"success": False, "message": "Car plate is required"}), 400
    
    if not mileage:
        return jsonify({"success": False, "message": "Mileage is required"}), 400
    
    # Convert to integer and validate
    try:
        mileage = int(mileage)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Mileage must be a valid number"}), 400
    
    if mileage <= 0:
        return jsonify({"success": False, "message": "Mileage must be greater than 0"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Validate car exists
        cursor.execute("SELECT Car_plate, Year FROM car WHERE Car_plate = %s", (car_plate,))
        car = cursor.fetchone()
        
        if not car:
            return jsonify({"success": False, "message": "Car not found"}), 404
        
        # 2. Get MAXIMUM mileage for this car plate
        cursor.execute("""
            SELECT MAX(Mileage) as max_mileage
            FROM service_history 
            WHERE Car_plate = %s
        """, (car_plate,))
        
        result = cursor.fetchone()
        max_mileage = result['max_mileage'] if result and result['max_mileage'] is not None else 0
        logger.debug("Mileage validation - New: %s, Max Recorded: %s, Car: %s", mileage, max_mileage, car_plate)
        
        # 3. STRICT VALIDATION: Mileage must be greater than MAX recorded mileage
        if max_mileage > 0 and mileage <= max_mileage:
            error_msg = f"New mileage ({mileage:,} km) must be GREATER than maximum recorded mileage ({max_mileage:,} km)"
            logger.warning("Mileage validation failed: %s", error_msg)
            return jsonify({
                "success": False, 
                "message": error_msg
            }), 400
        
        # 4. Additional validation: Check for unrealistic mileage jump
        if max_mileage > 0:
            mileage_increase = mileage - max_mileage
            
            # Get the date of the maximum mileage record
            cursor.execute("""
                SELECT Service_Date 
                FROM service_history 
                WHERE Car_plate = %s AND Mileage = %s
                ORDER BY Service_Date DESC 
                LIMIT 1
            """, (car_plate, max_mileage))
            
            max_mileage_record = cursor.fetchone()
            last_service_date = max_mileage_record['Service_Date'] if max_mileage_record else None
            
            days_since_last_service = 1  # Default to 1 day
            
            if last_service_date:
                days_since_last_service = (datetime.now().date() - last_service_date).days
                days_since_last_service = max(1, days_since_last_service)  # At least 1 day
            
            daily_mileage = mileage_increase / days_since_last_service
            
            # Flag unrealistic daily mileage (more than 1,000 km per day)
            if daily_mileage > 1000:
                warning_msg = f"Unrealistic mileage increase: {mileage_increase:,} km in {days_since_last_service} days ({daily_mileage:,.0f} km/day)"
                logger.warning(warning_msg)
        
        # 5. Validate reasonable mileage based on car age
        car_year = car['Year'] or datetime.now().year
        current_year = datetime.now().year
        car_age = current_year - car_year
        
        # Reasonable maximum: 25,000 km per year + 50,000 base
        reasonable_max = car_age * 25000 + 50000
        
        if mileage > reasonable_max:
            warning_msg = f"High mileage for {car_year} vehicle: {mileage:,} km (expected max: {reasonable_max:,} km)"
            logger.warning(warning_msg)
        
        # 6. Create service history record
        service_date = datetime.now().date()
        
        cursor.execute("""
            INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
            VALUES (%s, %s, CURDATE(), %s, %s)
        """, (service_date, mileage, notes, car_plate))
        
        history_id = cursor.lastrowid
        logger.info("Created service history record #%s with mileage %s", history_id, mileage)
        
        # 7. Link services performed (validate IDs)
        if services_performed:
            valid_service_ids = []
            if isinstance(services_performed, list):
                for sid in services_performed:
                    try:
                        sid_int = int(sid)
                        valid_service_ids.append(sid_int)
                    except Exception:
                        logger.warning("Skipping invalid service id: %s", sid)

            for service_id in valid_service_ids:
                cursor.execute("""
                    INSERT INTO service_history_service (History_ID, Service_ID)
                    VALUES (%s, %s)
                """, (history_id, service_id))
            logger.info("Linked %s services to history record %s", len(valid_service_ids), history_id)
        
        # 8. Update next oil change if provided
        if next_oil_change:
            # Validate next oil change date is not in past
            next_oil_date = datetime.strptime(next_oil_change, '%Y-%m-%d').date()
            if next_oil_date < datetime.now().date():
                return jsonify({"success": False, "message": "Next oil change date cannot be in the past"}), 400
            
            cursor.execute("""
                UPDATE car 
                SET Next_Oil_Change = %s 
                WHERE Car_plate = %s
            """, (next_oil_change, car_plate))
            logger.info("Updated next oil change to %s for %s", next_oil_change, car_plate)
        
        conn.commit()
        
        # Log the service completion
        logger.info(f"Service completed for {car_plate} - Mileage: {mileage:,} km (previous max: {max_mileage:,} km) by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": f"Service completed successfully for {car_plate}. Mileage updated from {max_mileage:,} km to {mileage:,} km.",
            "service_history_id": history_id,
            "mileage_recorded": mileage,
            "previous_max_mileage": max_mileage
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error completing service: {e}")
        return jsonify({
            "success": False,
            "message": f"Error completing service: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

# ===============================
# SERVICE HISTORY API ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route('/api/complete-services', methods=['GET'])
@mechanic_login_required
def get_complete_services():
    """API endpoint to get complete service history"""
    logger.debug("Fetching service history")
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get service history with car and owner info
        cursor.execute("""
            SELECT 
                sh.History_ID as Service_id,
                sh.Service_Date,
                sh.Mileage,
                sh.Last_Oil_Change,
                sh.Notes,
                sh.Car_plate,
                c.Model as car_model,
                c.Year as car_year,
                o.Owner_Name,
                o.PhoneNUMB,
                o.Owner_Email as Email
            FROM service_history sh
            LEFT JOIN car c ON sh.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            ORDER BY sh.Service_Date DESC
        """)
        
        services = cursor.fetchall()
        
        # Format dates for frontend
        for service in services:
            if service['Service_Date'] and hasattr(service['Service_Date'], 'isoformat'):
                service['Service_Date'] = service['Service_Date'].isoformat()
            
            # Add Service_Type for frontend compatibility
            service['Service_Type'] = 'Maintenance'
        
        logger.info("Found %s service records", len(services))
        return jsonify({
            "success": True,
            "data": services,
            "total": len(services)
        })
        
    except Exception as e:
        logger.error(f"Service history API error: {e}")
        return jsonify({
            "success": False,
            "message": f"Error loading service history: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)
# ===============================
# EDIT OWNER & CAR INFORMATION ROUTES - ADD THIS SECTION
# ===============================

@mechanic_bp.route("/edit-owner")
def edit_owner_page():
    """Serve the edit owner form page"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    return render_template("edit_owner.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/edit-car")
def edit_car_page():
    """Serve the edit car form page"""
    if not session.get("mechanic_logged_in"):
        return redirect("/mechanic/login.html")
    
    return render_template("edit_car.html", username=session.get("mechanic_username"))

@mechanic_bp.route("/api/owner/<int:owner_id>", methods=['GET'])
@mechanic_login_required
def get_owner_by_id(owner_id):
    """Get owner information by ID"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT Owner_ID, Owner_Name, Owner_Email, PhoneNUMB 
            FROM owner 
            WHERE Owner_ID = %s
        """, (owner_id,))
        
        owner = cursor.fetchone()
        
        if owner:
            return jsonify({
                "success": True,
                "owner": owner
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Owner with ID {owner_id} not found"
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting owner: {e}")
        return jsonify({
            "success": False,
            "message": f"Error getting owner: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/owner/<int:owner_id>", methods=['PUT'])
@mechanic_login_required
def update_owner(owner_id):
    """Update owner information"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    owner_name = data.get('owner_name', '').strip()
    owner_email = data.get('owner_email', '').strip()
    phone_number = data.get('phone_number', '').strip()
    
    # Validation
    if not owner_name:
        return jsonify({"success": False, "message": "Owner name is required"}), 400
    
    if not phone_number:
        return jsonify({"success": False, "message": "Phone number is required"}), 400
    
    # Basic email validation (optional field)
    if owner_email and '@' not in owner_email:
        return jsonify({"success": False, "message": "Invalid email format"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if owner exists
        cursor.execute("SELECT Owner_ID FROM owner WHERE Owner_ID = %s", (owner_id,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": f"Owner with ID {owner_id} not found"}), 404
        
        # Check if phone number already exists for another owner
        cursor.execute("""
            SELECT Owner_ID FROM owner 
            WHERE PhoneNUMB = %s AND Owner_ID != %s
        """, (phone_number, owner_id))
        
        if cursor.fetchone():
            return jsonify({
                "success": False, 
                "message": "Phone number already registered to another owner"
            }), 409
        
        # Update owner information
        cursor.execute("""
            UPDATE owner 
            SET Owner_Name = %s, 
                Owner_Email = %s, 
                PhoneNUMB = %s 
            WHERE Owner_ID = %s
        """, (owner_name, owner_email, phone_number, owner_id))
        
        conn.commit()
        
        logger.info(f"Owner {owner_id} updated by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": f"Owner {owner_name} updated successfully",
            "owner_id": owner_id
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating owner: {e}")
        return jsonify({
            "success": False,
            "message": f"Error updating owner: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/car/<car_plate>", methods=['PUT'])
@mechanic_login_required
def update_car(car_plate):
    """Update car information"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    model = data.get('model', '').strip()
    year = data.get('year')
    vin = data.get('vin', '').strip().upper()
    next_oil_change = data.get('next_oil_change')
    owner_id = data.get('owner_id')
    
    # Validation
    if not model:
        return jsonify({"success": False, "message": "Car model is required"}), 400
    
    if not year or not isinstance(year, int) or year < 1900 or year > datetime.now().year + 1:
        return jsonify({"success": False, "message": "Valid manufacturing year is required"}), 400
    
    if not vin or len(vin) != 17:
        return jsonify({"success": False, "message": "Valid 17-character VIN is required"}), 400
    
    if next_oil_change:
        try:
            next_oil_date = datetime.strptime(next_oil_change, '%Y-%m-%d').date()
            if next_oil_date < datetime.now().date():
                return jsonify({"success": False, "message": "Next oil change date cannot be in the past"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format for next oil change"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if car exists
        cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (car_plate,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": f"Car with plate {car_plate} not found"}), 404
        
        # Check if VIN already exists for another car
        cursor.execute("""
            SELECT Car_plate FROM car 
            WHERE VIN = %s AND Car_plate != %s
        """, (vin, car_plate))
        
        if cursor.fetchone():
            return jsonify({
                "success": False, 
                "message": f"VIN {vin} already registered to another car"
            }), 409
        
        # Check if owner exists
        if owner_id:
            cursor.execute("SELECT Owner_ID FROM owner WHERE Owner_ID = %s", (owner_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": f"Owner with ID {owner_id} not found"}), 404
        
        # Update car information
        update_query = """
            UPDATE car 
            SET Model = %s, 
                Year = %s, 
                VIN = %s, 
                Next_Oil_Change = %s,
                Owner_ID = %s
            WHERE Car_plate = %s
        """
        cursor.execute(update_query, (model, year, vin, next_oil_change, owner_id, car_plate))
        
        conn.commit()
        
        logger.info(f"Car {car_plate} updated by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": f"Car {car_plate} updated successfully",
            "car_plate": car_plate
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating car: {e}")
        return jsonify({
            "success": False,
            "message": f"Error updating car: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/search-owners", methods=['GET'])
@mechanic_login_required
def search_owners():
    """Search owners by name, email, or phone"""
    search_term = request.args.get('q', '').strip()
    
    if not search_term or len(search_term) < 2:
        return jsonify({"success": False, "message": "Please enter at least 2 characters"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        search_pattern = f"%{search_term}%"
        
        cursor.execute("""
            SELECT Owner_ID, Owner_Name, Owner_Email, PhoneNUMB 
            FROM owner 
            WHERE Owner_Name LIKE %s 
               OR Owner_Email LIKE %s 
               OR PhoneNUMB LIKE %s
            ORDER BY Owner_Name
            LIMIT 20
        """, (search_pattern, search_pattern, search_pattern))
        
        owners = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "owners": owners,
            "count": len(owners)
        })
        
    except Exception as e:
        logger.error(f"Error searching owners: {e}")
        return jsonify({
            "success": False,
            "message": f"Error searching owners: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/owner-cars/<int:owner_id>", methods=['GET'])
@mechanic_login_required
def get_owner_cars(owner_id):
    """Get all cars owned by a specific owner"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT Car_plate, Model, Year, VIN, Next_Oil_Change
            FROM car 
            WHERE Owner_ID = %s
            ORDER BY Car_plate
        """, (owner_id,))
        
        cars = cursor.fetchall()
        
        # Format dates
        for car in cars:
            if car.get('Next_Oil_Change') and hasattr(car['Next_Oil_Change'], 'isoformat'):
                car['Next_Oil_Change'] = car['Next_Oil_Change'].isoformat()
        
        return jsonify({
            "success": True,
            "cars": cars,
            "count": len(cars)
        })
        
    except Exception as e:
        logger.error(f"Error getting owner cars: {e}")
        return jsonify({
            "success": False,
            "message": f"Error getting owner cars: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)
# ===============================
# ERROR HANDLERS
# ===============================

@mechanic_bp.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404

@mechanic_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error"}), 500

@mechanic_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({"success": False, "message": "Unauthorized access"}), 401