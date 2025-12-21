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


def add_months(date, months):
    """Safely add months to a date, handling year rollovers and varying month lengths"""
    month = date.month - 1 + months
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime(year, month, day).date()
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
        
        # Today's services count - ONLY from service_history table (after-service form)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM service_history 
            WHERE DATE(Service_Date) = CURDATE()
        """)
        today_services_result = cursor.fetchone()
        today_services = today_services_result[0] if today_services_result else 0
        
        # Completed this week - ONLY from service_history table
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM service_history 
            WHERE YEARWEEK(Service_Date, 1) = YEARWEEK(CURDATE(), 1)
        """)
        completed_week_result = cursor.fetchone()
        completed_week = completed_week_result[0] if completed_week_result else 0
        
        # Today's appointments - This is separate from services
        cursor.execute("SELECT COUNT(*) as count FROM appointment WHERE Date = CURDATE()")
        today_appointments_result = cursor.fetchone()
        today_appointments = today_appointments_result[0] if today_appointments_result else 0
        
        # Total appointments - Separate from services
        cursor.execute("SELECT COUNT(*) as count FROM appointment")
        total_appointments_result = cursor.fetchone()
        total_appointments = total_appointments_result[0] if total_appointments_result else 0
        
        # Urgent jobs (overdue oil changes) - Based on car table
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
        
        # Total services performed (all time) - from service_history
        cursor.execute("SELECT COUNT(*) as count FROM service_history")
        total_services_result = cursor.fetchone()
        total_services = total_services_result[0] if total_services_result else 0
        
        # Services pending (appointments) - This is separate
        cursor.execute("SELECT COUNT(*) as count FROM appointment WHERE Date >= CURDATE()")
        pending_services_result = cursor.fetchone()
        pending_services = pending_services_result[0] if pending_services_result else 0
        
        logger.info("Stats - Today Services: %s, Week: %s, Today Appointments: %s", 
                   today_services, completed_week, today_appointments)
        
        return jsonify({
            "success": True,
            "data": {
                "today_services": today_services,  # Services completed today (from service_history)
                "completed_week": completed_week,  # Services completed this week (from service_history)
                "today_appointments": today_appointments,  # Appointments scheduled for today
                "pending_services": pending_services,  # Future appointments
                "urgent_jobs": urgent_jobs,  # Cars with overdue oil changes
                "total_cars": total_cars,
                "total_owners": total_owners,
                "total_services": total_services  # All services ever performed
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
    """API endpoint for recent activity with REAL data - DEBUGGED VERSION"""
    logger.info("Recent activity requested - DEBUGGED VERSION")

    # Safely parse pagination params
    try:
        limit = int(request.args.get('limit', 10))
    except Exception:
        limit = 10
    
    try:
        offset = int(request.args.get('offset', 0))
    except Exception:
        offset = 0

    # cap limit to avoid heavy queries
    max_limit = 50
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

        # ============================================
        # SIMPLIFIED QUERY - FIXED VERSION
        # ============================================
        
        # Get recent service history (most reliable source)
        cursor.execute('''
            SELECT 
                sh.History_ID,
                sh.Service_Date as timestamp,
                sh.Car_plate as plate,
                sh.Mileage,
                sh.Notes,
                c.Model as car_model,
                o.Owner_Name as owner_name
            FROM service_history sh
            LEFT JOIN car c ON sh.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            ORDER BY sh.Service_Date DESC
            LIMIT %s OFFSET %s
        ''', (limit, offset))

        activities = cursor.fetchall()
        logger.info(f"Found {len(activities)} service history records")
        
        # ============================================
        # FORMAT ACTIVITIES PROPERLY
        # ============================================
        formatted_activities = []
        
        for activity in activities:
            timestamp = activity.get('timestamp')
            
            # Format timestamp
            if timestamp:
                if hasattr(timestamp, 'isoformat'):
                    timestamp_str = timestamp.isoformat()
                else:
                    timestamp_str = str(timestamp)
            else:
                timestamp_str = datetime.now().isoformat()
            
            # Create meaningful description
            plate = activity.get('plate', 'Unknown')
            car_model = activity.get('car_model', '')
            owner = activity.get('owner_name', '')
            mileage = activity.get('Mileage')
            notes = activity.get('Notes', '')
            
            description = f"Service completed for {plate}"
            if car_model:
                description += f" ({car_model})"
            if owner:
                description += f" - Owner: {owner}"
            if mileage:
                description += f" - Mileage: {mileage:,} km"
            if notes and notes.strip() and notes.strip().lower() != 'initial car registration':
                description += f" - Notes: {notes}"
            
            # Determine icon based on notes/content
            icon = "🛠️"  # Default service icon
            if "oil" in notes.lower():
                icon = "⛽"
            elif "tire" in notes.lower():
                icon = "🌀"
            elif "brake" in notes.lower():
                icon = "🛑"
            
            formatted_activities.append({
                "type": "service",
                "title": "Service Completed",
                "description": description,
                "timestamp": timestamp_str,
                "plate": plate,
                "owner": owner,
                "mileage": mileage,
                "icon": icon,
                "id": activity.get('History_ID')
            })
        
        # If no service history, get some appointments as fallback
        if len(formatted_activities) < 5:
            logger.info("Few service records, fetching appointments as well")
            cursor.execute('''
                SELECT 
                    a.Appointment_ID,
                    a.Date as appointment_date,
                    a.Time as appointment_time,
                    a.Car_plate as plate,
                    a.Notes,
                    c.Model as car_model,
                    o.Owner_Name as owner_name
                FROM appointment a
                LEFT JOIN car c ON a.Car_plate = c.Car_plate
                LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
                WHERE a.Date >= CURDATE()
                ORDER BY a.Date, a.Time
                LIMIT 5
            ''')
            
            appointments = cursor.fetchall()
            
            for appointment in appointments:
                date = appointment.get('appointment_date')
                time = appointment.get('appointment_time')
                
                # Format timestamp
                timestamp_str = ""
                if date:
                    if hasattr(date, 'isoformat'):
                        timestamp_str = date.isoformat()
                    else:
                        timestamp_str = str(date)
                
                plate = appointment.get('plate', 'Unknown')
                car_model = appointment.get('car_model', '')
                owner = appointment.get('owner_name', '')
                
                # Format time if available
                time_str = ""
                if time:
                    if isinstance(time, timedelta):
                        total_seconds = int(time.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        time_str = f"{hours:02d}:{minutes:02d}"
                    else:
                        time_str = str(time)
                
                description = f"Appointment scheduled for {plate}"
                if car_model:
                    description += f" ({car_model})"
                if owner:
                    description += f" - Owner: {owner}"
                if time_str:
                    description += f" at {time_str}"
                
                formatted_activities.append({
                    "type": "appointment",
                    "title": "Upcoming Appointment",
                    "description": description,
                    "timestamp": timestamp_str,
                    "plate": plate,
                    "owner": owner,
                    "icon": "📅",
                    "id": appointment.get('Appointment_ID')
                })
        
        # Sort all activities by timestamp (most recent first)
        formatted_activities.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit to requested number
        formatted_activities = formatted_activities[:limit]
        
        logger.info("Returning %d formatted activities", len(formatted_activities))
        
        # If still no activities, add a helpful placeholder
        if not formatted_activities:
            logger.info("No activities found, adding placeholder")
            formatted_activities.append({
                "type": "info",
                "title": "Welcome to the System!",
                "description": "No activities yet. Start by adding a car or completing a service.",
                "timestamp": datetime.now().isoformat(),
                "icon": "👋",
                "is_placeholder": True
            })
        
        return jsonify({
            "success": True,
            "data": formatted_activities,
            "total": len(formatted_activities),
            "message": f"Found {len(formatted_activities)} activities"
        })

    except Error as db_err:
        logger.exception("Database error while loading recent activities: %s", str(db_err))
        # Return empty data instead of error for better UX
        return jsonify({
            "success": True,
            "data": [{
                "type": "error",
                "title": "Database Connection Issue",
                "description": "Temporary issue loading activities. Please try again.",
                "timestamp": datetime.now().isoformat(),
                "icon": "⚠️",
                "is_error": True
            }],
            "total": 1,
            "message": "Database connection issue"
        })
        
    except Exception as e:
        logger.exception("Unhandled error in recent activities: %s", str(e))
        # Return graceful error response
        return jsonify({
            "success": False,
            "message": f"Error loading activities: {str(e)}",
            "error": str(e)
        }), 500
        
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
    """Update appointment with time slot availability checking"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    date = data.get('date')
    time = data.get('time')
    notes = data.get('notes', '')
    
    # Validate date format and not in the past
    if date:
        try:
            appt_date = datetime.strptime(date, '%Y-%m-%d').date()
            if appt_date < datetime.now().date():
                return jsonify({
                    "success": False,
                    "message": "Cannot update appointment to a past date. Please select a future date."
                }), 400
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid date format. Use YYYY-MM-DD"
            }), 400
    
    # Validate time format if provided
    if time:
        try:
            datetime.strptime(time, '%H:%M')
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid time format. Use HH:MM (24-hour format)"
            }), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get current appointment details to check if date/time are being changed
        cursor.execute("""
            SELECT Appointment_ID, Date, Time, Car_plate 
            FROM appointment 
            WHERE Appointment_ID = %s
        """, (appointment_id,))
        
        current_appointment = cursor.fetchone()
        if not current_appointment:
            return jsonify({
                "success": False,
                "message": f"Appointment #{appointment_id} not found"
            }), 404
        
        # 2. Check time slot availability ONLY if date or time are being changed
        current_date = current_appointment['Date']
        current_time = current_appointment['Time']
        
        # Convert timedelta to string for comparison if needed
        if current_time and isinstance(current_time, timedelta):
            total_seconds = int(current_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            current_time_str = f"{hours:02d}:{minutes:02d}"
        else:
            current_time_str = str(current_time) if current_time else None
        
        # Check if date or time are actually being changed
        date_changed = (date and date != str(current_date))
        time_changed = (time and time != current_time_str)
        
        if date_changed or time_changed:
            # Time slot check: find conflicting appointments on same date/time
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM appointment 
                WHERE Date = %s 
                  AND Time = %s 
                  AND Appointment_ID != %s
            """, (date or current_date, time or current_time_str, appointment_id))
            
            conflict_result = cursor.fetchone()
            conflict_count = conflict_result['count'] if conflict_result else 0
            
            if conflict_count > 0:
                return jsonify({
                    "success": False,
                    "message": f"Time slot unavailable. Another appointment is already booked for {date or current_date} at {time or current_time_str}."
                }), 409
        
        # 3. Update appointment if no conflicts
        update_query = """
            UPDATE appointment 
            SET Date = %s, Time = %s, Notes = %s 
            WHERE Appointment_ID = %s
        """
        cursor.execute(update_query, (date or current_date, time or current_time_str, notes, appointment_id))
        
        conn.commit()
        
        logger.info(f"Appointment {appointment_id} updated by {session.get('mechanic_username')} - Date: {date or current_date}, Time: {time or current_time_str}")
        
        return jsonify({
            "success": True,
            "message": "Appointment updated successfully",
            "appointment_id": appointment_id
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating appointment: {e}")
        return jsonify({
            "success": False,
            "message": "Error updating appointment"
        }), 500
    finally:
        _safe_close(cursor, conn)

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
        
@mechanic_bp.route("/addCar.html")
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


@mechanic_bp.route("/api/add-car", methods=["POST"])
@mechanic_login_required
def add_car():
    """Add new car to database - WITH COMPLETE DUPLICATE CHECKS - NO SERVICE HISTORY CREATION"""
    logger.info("Adding new car to database")
    
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    # Extract data matching frontend form
    car_plate = data.get('car_plate', '').strip().upper()
    model = data.get('model', '').strip()
    year = data.get('year')
    vin = data.get('vin', '').strip()
    next_oil_change = data.get('next_oil_change')  # Can be empty
    owner_type = data.get('owner_type')
    phone_number = (data.get('phone_number') or data.get('PhoneNUMB') or data.get('phone') or '').strip()
    current_mileage = data.get('current_mileage')  # Still collect but don't create service history
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
    
    # Phone number validation
    phone_clean = re.sub(r'[+\s\-()]', '', phone_number)
    if len(phone_clean) < 8:
        return jsonify({"status": "error", "message": "Phone number is too short (minimum 8 digits)"}), 400
    
    if len(phone_clean) > 20:
        return jsonify({"status": "error", "message": "Phone number is too long (max 20 characters)"}), 400
    
    if not phone_clean.isdigit() and not phone_clean.startswith('+'):
        return jsonify({"status": "error", "message": "Phone number should contain only digits and optional '+' prefix"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # helper to tolerate mocked cursors
        def _safe_fetchone():
            try:
                return cursor.fetchone()
            except Exception:
                return None

        # ============================================
        # DUPLICATE CHECK 1: Car plate
        # ============================================
        cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE Car_plate = %s", (car_plate,))
        existing_car = _safe_fetchone()
        if existing_car:
            # Get owner name for better error message
            cursor.execute("SELECT Owner_Name FROM owner WHERE Owner_ID = %s", (existing_car['Owner_ID'],))
            existing_owner = _safe_fetchone()
            owner_name_msg = existing_owner['Owner_Name'] if existing_owner else 'Unknown'
            return jsonify({"status": "error", "message": f"Car with plate {car_plate} already exists (Owner: {owner_name_msg})"}), 409

        # ============================================
        # DUPLICATE CHECK 2: VIN
        # ============================================
        cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE VIN = %s", (vin,))
        existing_vin = _safe_fetchone()
        if existing_vin:
            # Get owner name for better error message
            cursor.execute("SELECT Owner_Name FROM owner WHERE Owner_ID = %s", (existing_vin['Owner_ID'],))
            existing_owner = _safe_fetchone()
            owner_name_msg = existing_owner['Owner_Name'] if existing_owner else 'Unknown'
            return jsonify({"status": "error", "message": f"VIN {vin} already registered to car: {existing_vin['Car_plate']} (Owner: {owner_name_msg})"}), 409
        
        # REMOVE THE AUTOSTART TRANSACTION - FIXED HERE
        try:
            autocommit_before = conn.autocommit
            if not autocommit_before:
                logger.info("Connection already in transaction mode, proceeding...")
            else:
                conn.start_transaction()
                logger.info("Started new transaction")
        except Exception as tx_error:
            logger.warning(f"Transaction check failed: {tx_error}. Continuing...")
        
        owner_id = None
        
        if owner_type == "existing":
            # Find existing owner by phone number
            cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE PhoneNUMB = %s", (phone_number,))
            existing_owner = _safe_fetchone()
            if existing_owner:
                owner_id = existing_owner['Owner_ID']
                logger.info("Found existing owner ID: %s", owner_id)
            else:
                # ROLLBACK IF WE STARTED TRANSACTION
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except:
                    pass
                return jsonify({"status": "error", "message": "No existing owner found with this phone number"}), 404
                
        else:  # new owner
            # ============================================
            # DUPLICATE CHECK 3: Phone number for new owner
            # ============================================
            cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE PhoneNUMB = %s", (phone_number,))
            existing_owner_by_phone = _safe_fetchone()
            if existing_owner_by_phone:
                # ROLLBACK IF WE STARTED TRANSACTION
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except:
                    pass
                return jsonify({
                    "status": "error", 
                    "message": f"Phone number already registered to owner: {existing_owner_by_phone['Owner_Name']} (ID: {existing_owner_by_phone['Owner_ID']})"
                }), 409
            
            # ============================================
            # DUPLICATE CHECK 4: Email for new owner (if provided)
            # ============================================
            if owner_email:
                cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE Owner_Email = %s", (owner_email,))
                existing_owner_by_email = _safe_fetchone()
                if existing_owner_by_email:
                    # ROLLBACK IF WE STARTED TRANSACTION
                    try:
                        if conn.in_transaction:
                            conn.rollback()
                    except:
                        pass
                    return jsonify({
                        "status": "error", 
                        "message": f"Email already registered to owner: {existing_owner_by_email['Owner_Name']} (ID: {existing_owner_by_email['Owner_ID']})"
                    }), 409
            
            # Create new owner
            cursor.execute("""
                INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB)
                VALUES (%s, %s, %s)
            """, (owner_name, owner_email, phone_number))
            owner_id = cursor.lastrowid
            logger.info("Created new owner ID: %s", owner_id)
        
        # NEW FEATURE: Calculate next oil change date if not provided
        auto_calculated = False
        if next_oil_change is None or (isinstance(next_oil_change, str) and next_oil_change.strip() == ''):
            # User didn't provide a date, so we auto-calculate
            base_date = None
            if last_service_date:
                try:
                    base_date = datetime.strptime(last_service_date, '%Y-%m-%d').date()
                except Exception:
                    base_date = datetime.now().date()
            else:
                base_date = datetime.now().date()
            
            next_oil_change = add_months(base_date, 3)
            auto_calculated = True
            logger.info(f"Auto-calculated next oil change: {next_oil_change} (+3 months from {base_date})")
        else:
            # User provided a date, ensure it's valid
            try:
                datetime.strptime(next_oil_change, '%Y-%m-%d')
            except ValueError:
                # ROLLBACK IF WE STARTED TRANSACTION
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except:
                    pass
                return jsonify({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}), 400
        
        # Add the car
        cursor.execute("""
            INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_ID)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (car_plate, model, year, vin, next_oil_change, owner_id))
        
        # ============================================
        # CRITICAL CHANGE: DO NOT CREATE SERVICE HISTORY RECORD
        # ============================================
        # We're removing this block to prevent dashboard counting
        # The initial mileage is still saved in the form data but not in service_history
        
        # if current_mileage is not None and current_mileage != '':
        #     # coerce mileage to int
        #     try:
        #         cm = int(current_mileage)
        #     except Exception:
        #         cm = None
        #
        #     if cm is not None:
        #         # parse last_service_date if string
        #         svc_date = None
        #         if last_service_date:
        #             try:
        #                 svc_date = datetime.strptime(last_service_date, '%Y-%m-%d').date()
        #             except Exception:
        #                 svc_date = None
        #         svc_date = svc_date or datetime.now().date()
        #
        #         cursor.execute("""
        #             INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
        #             VALUES (%s, %s, CURDATE(), %s, %s)
        #         """, (svc_date, cm, service_notes, car_plate))
        #         
        #         history_id = cursor.lastrowid
        #         logger.info("Created initial service history record #%s", history_id)
        # ============================================
        
        # COMMIT ONLY IF WE STARTED TRANSACTION
        try:
            if conn.in_transaction:
                conn.commit()
                logger.info("Transaction committed successfully")
            else:
                # Connection is already autocommit or in managed transaction
                conn.commit()
        except Exception as commit_error:
            logger.warning(f"Commit handling: {commit_error}")
            try:
                if not conn.autocommit:
                    conn.commit()
            except:
                pass
        
        # Clear the stored plate from session
        session.pop('detected_plate', None)
        
        # Log the action
        logger.info(f"New car added: {car_plate} by user {session.get('mechanic_username')}. Next oil: {next_oil_change}" +
                   (" (auto-calculated)" if auto_calculated else ""))
        
        response_message = f"Car {car_plate} added successfully to database"
        if auto_calculated:
            response_message = f"Car {car_plate} added successfully. Next oil change auto-scheduled for {next_oil_change} (+3 months)."
        
        return jsonify({
            "status": "success",
            "message": response_message,
            "car_plate": car_plate,
            "owner_id": owner_id,
            "next_oil_change": str(next_oil_change),
            "auto_calculated": auto_calculated,
            "note": "Initial mileage recorded but no service history created (dashboard will not count this)"
        })
        
    except Exception as e:
        # ROLLBACK ON ERROR
        try:
            if conn and conn.in_transaction:
                conn.rollback()
                logger.info("Transaction rolled back due to error")
        except:
            pass
        
        logger.error(f"Error adding car: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Error adding car: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)
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
# ADD NEW OWNER ROUTES - MECHANIC SESSION ONLY
# ===============================

@mechanic_bp.route("/api/owner", methods=['POST'])
@mechanic_login_required
def add_owner():
    """Create a new owner with optional car - WITH DUPLICATE CHECKS"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    owner_name = data.get('owner_name', '').strip()
    owner_email = data.get('owner_email', '').strip()
    phone_number = data.get('phone_number', '').strip()
    car_data = data.get('car')  # Optional car data
    
    # Input validation with detailed error messages
    if not owner_name:
        return jsonify({"success": False, "message": "Owner name is required"}), 400
    
    # Name length and character validation
    if len(owner_name) > 100:
        return jsonify({"success": False, "message": "Owner name is too long (max 100 characters)"}), 400
    
    # Check for malicious input in name
    if re.search(r'[<>{}[\];]', owner_name):
        return jsonify({"success": False, "message": "Owner name contains invalid characters"}), 400
    
    # Phone number validation
    if not phone_number:
        return jsonify({"success": False, "message": "Phone number is required"}), 400
    
    # Clean phone number (remove spaces, dashes, parentheses)
    phone_clean = re.sub(r'[+\s\-()]', '', phone_number)
    
    if len(phone_clean) < 8:
        return jsonify({"success": False, "message": "Phone number is too short (minimum 8 digits)"}), 400
    
    if len(phone_clean) > 20:
        return jsonify({"success": False, "message": "Phone number is too long (max 20 characters)"}), 400
    
    if not phone_clean.isdigit() and not phone_clean.startswith('+'):
        return jsonify({"success": False, "message": "Phone number should contain only digits and optional '+' prefix"}), 400
    
    # Email validation (optional)
    if owner_email:
        if len(owner_email) > 100:
            return jsonify({"success": False, "message": "Email address is too long"}), 400
        
        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, owner_email):
            return jsonify({"success": False, "message": "Invalid email format. Please use a valid email address"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # ============================================
        # DUPLICATE CHECK 1: Phone number
        # ============================================
        cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE PhoneNUMB = %s", (phone_number,))
        existing_owner_by_phone = cursor.fetchone()
        if existing_owner_by_phone:
            return jsonify({
                "success": False, 
                "message": f"Phone number already registered to owner: {existing_owner_by_phone['Owner_Name']} (ID: {existing_owner_by_phone['Owner_ID']})"
            }), 409
        
        # ============================================
        # DUPLICATE CHECK 2: Email (if provided)
        # ============================================
        if owner_email:
            cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE Owner_Email = %s", (owner_email,))
            existing_owner_by_email = cursor.fetchone()
            if existing_owner_by_email:
                return jsonify({
                    "success": False, 
                    "message": f"Email already registered to owner: {existing_owner_by_email['Owner_Name']} (ID: {existing_owner_by_email['Owner_ID']})"
                }), 409
        
        # ============================================
        # Create new owner
        # ============================================
        cursor.execute("""
            INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB)
            VALUES (%s, %s, %s)
        """, (owner_name, owner_email if owner_email else None, phone_number))
        
        owner_id = cursor.lastrowid
        
        # If car data is provided, add car as well
        car_added = False
        car_plate = None
        
        if car_data and isinstance(car_data, dict):
            car_plate = car_data.get('car_plate', '').strip().upper()
            model = car_data.get('model', '').strip()
            year = car_data.get('year')
            vin = car_data.get('vin', '').strip().upper()
            
            # Validate car data if provided
            if car_plate:
                # Validate car plate format
                if not re.match(r'^[A-Z]{1}[0-9]{1,6}$', car_plate):
                    return jsonify({
                        "success": False, 
                        "message": "Valid license plate is required (1 letter followed by 1-6 digits)"
                    }), 400
                
                # ============================================
                # DUPLICATE CHECK 3: Car plate
                # ============================================
                cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE Car_plate = %s", (car_plate,))
                existing_car = cursor.fetchone()
                if existing_car:
                    # Get owner name for better error message
                    cursor.execute("SELECT Owner_Name FROM owner WHERE Owner_ID = %s", (existing_car['Owner_ID'],))
                    existing_owner = cursor.fetchone()
                    owner_name_msg = existing_owner['Owner_Name'] if existing_owner else 'Unknown'
                    return jsonify({
                        "success": False, 
                        "message": f"Car with plate {car_plate} already exists (Owner: {owner_name_msg})"
                    }), 409
                
                # VIN validation if provided
                if vin:
                    if len(vin) != 17:
                        return jsonify({
                            "success": False, 
                            "message": "VIN must be exactly 17 characters"
                        }), 400
                    
                    # ============================================
                    # DUPLICATE CHECK 4: VIN
                    # ============================================
                    cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE VIN = %s", (vin,))
                    existing_vin = cursor.fetchone()
                    if existing_vin:
                        # Get owner name for better error message
                        cursor.execute("SELECT Owner_Name FROM owner WHERE Owner_ID = %s", (existing_vin['Owner_ID'],))
                        existing_owner = cursor.fetchone()
                        owner_name_msg = existing_owner['Owner_Name'] if existing_owner else 'Unknown'
                        return jsonify({
                            "success": False, 
                            "message": f"VIN {vin} already registered to car: {existing_vin['Car_plate']} (Owner: {owner_name_msg})"
                        }), 409
                
                # Model validation
                if not model:
                    return jsonify({"success": False, "message": "Car model is required when adding a car"}), 400
                
                if len(model) > 50:
                    return jsonify({"success": False, "message": "Car model name is too long (max 50 characters)"}), 400
                
                # Year validation
                try:
                    if year:
                        year = int(year)
                        current_year = datetime.now().year
                        if year < 1900 or year > current_year + 1:
                            return jsonify({
                                "success": False, 
                                "message": f"Year must be between 1900 and {current_year + 1}"
                            }), 400
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Year must be a valid number"}), 400
                
                # Insert car
                cursor.execute("""
                    INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_ID)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (car_plate, model, year if year else None, vin if vin else None, None, owner_id))
                
                car_added = True
                logger.info(f"Car {car_plate} added with new owner {owner_name}")
        
        conn.commit()
        
        message = f"Owner '{owner_name}' added successfully"
        if car_added:
            message += f" with car '{car_plate}'"
        
        logger.info(f"New owner added: {owner_name} (ID: {owner_id}) by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": message,
            "owner_id": owner_id,
            "owner": {
                "Owner_ID": owner_id,
                "Owner_Name": owner_name,
                "Owner_Email": owner_email,
                "PhoneNUMB": phone_number
            },
            "car_added": car_added,
            "car_plate": car_plate if car_added else None
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error adding owner: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Error adding owner: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/owner/<int:owner_id>", methods=['DELETE'])
@mechanic_login_required
def delete_owner(owner_id):
    """Delete an owner while keeping their cars (cars become ownerless)"""
    if not isinstance(owner_id, int) or owner_id <= 0:
        return jsonify({
            "success": False,
            "message": "Invalid owner ID"
        }), 400
    
    # Get owner name for confirmation message
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # First, get owner name for logging/messages
        cursor.execute("SELECT Owner_Name, PhoneNUMB FROM owner WHERE Owner_ID = %s", (owner_id,))
        owner = cursor.fetchone()
        
        if not owner:
            return jsonify({
                "success": False,
                "message": f"Owner with ID {owner_id} not found"
            }), 404
        
        owner_name = owner['Owner_Name']
        phone_number = owner['PhoneNUMB']
        
        # Check how many cars this owner has
        cursor.execute("SELECT COUNT(*) as car_count FROM car WHERE Owner_ID = %s", (owner_id,))
        car_count = cursor.fetchone()['car_count']
        
        # Check if owner has admin accounts
        cursor.execute("SELECT COUNT(*) as admin_count FROM admin WHERE Owner_ID = %s", (owner_id,))
        admin_count = cursor.fetchone()['admin_count']
        
        if admin_count > 0:
            return jsonify({
                "success": False,
                "message": f"Cannot delete owner '{owner_name}' - they have {admin_count} admin account(s). Remove admin accounts first.",
                "has_admin_accounts": True,
                "admin_count": admin_count
            }), 400
        
        # IMPORTANT: Set cars to NULL owner first (so they remain in the system)
        if car_count > 0:
            cursor.execute("""
                UPDATE car 
                SET Owner_ID = NULL 
                WHERE Owner_ID = %s
            """, (owner_id,))
            logger.info(f"Set {car_count} cars to ownerless for owner ID {owner_id}")
        
        # Now delete the owner
        cursor.execute("DELETE FROM owner WHERE Owner_ID = %s", (owner_id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        
        logger.info(f"Owner '{owner_name}' (ID: {owner_id}, Phone: {phone_number}) deleted by {session.get('mechanic_username')}. {car_count} cars set to ownerless.")
        
        return jsonify({
            "success": True,
            "message": f"Owner '{owner_name}' deleted successfully. {car_count} car(s) are now ownerless and remain in the system.",
            "owner_id": owner_id,
            "owner_name": owner_name,
            "cars_affected": car_count,
            "cars_set_to_ownerless": car_count > 0
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error deleting owner: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Error deleting owner: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)


@mechanic_bp.route("/api/owner-without-car", methods=['POST'])
@mechanic_login_required
def add_owner_without_car():
    """Add a new owner without a car (simplified version)"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    owner_name = data.get('owner_name', '').strip()
    owner_email = data.get('owner_email', '').strip()
    phone_number = data.get('phone_number', '').strip()
    
    # Input validation
    if not owner_name:
        return jsonify({"success": False, "message": "Owner name is required"}), 400
    
    if len(owner_name) > 100:
        return jsonify({"success": False, "message": "Owner name is too long (max 100 characters)"}), 400
    
    if not phone_number:
        return jsonify({"success": False, "message": "Phone number is required"}), 400
    
    # Clean and validate phone
    phone_clean = re.sub(r'[+\s\-()]', '', phone_number)
    if len(phone_clean) < 8:
        return jsonify({"success": False, "message": "Phone number is too short (minimum 8 digits)"}), 400
    
    if len(phone_clean) > 20:
        return jsonify({"success": False, "message": "Phone number is too long (max 20 characters)"}), 400
    
    # Email validation (optional)
    if owner_email:
        if len(owner_email) > 100:
            return jsonify({"success": False, "message": "Email address is too long"}), 400
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, owner_email):
            return jsonify({"success": False, "message": "Invalid email format"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if owner with same phone already exists
        cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE PhoneNUMB = %s", (phone_number,))
        existing_owner = cursor.fetchone()
        if existing_owner:
            return jsonify({
                "success": False, 
                "message": f"Phone number already registered to owner: {existing_owner['Owner_Name']} (ID: {existing_owner['Owner_ID']})"
            }), 409
        
        # Check if owner with same email already exists (if email provided)
        if owner_email:
            cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE Owner_Email = %s", (owner_email,))
            existing_email = cursor.fetchone()
            if existing_email:
                return jsonify({
                    "success": False, 
                    "message": f"Email already registered to owner: {existing_email['Owner_Name']} (ID: {existing_email['Owner_ID']})"
                }), 409
        
        # Create new owner
        cursor.execute("""
            INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB)
            VALUES (%s, %s, %s)
        """, (owner_name, owner_email if owner_email else None, phone_number))
        
        owner_id = cursor.lastrowid
        conn.commit()
        
        logger.info(f"New owner added without car: {owner_name} (ID: {owner_id}) by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": f"Owner '{owner_name}' added successfully",
            "owner_id": owner_id,
            "owner": {
                "Owner_ID": owner_id,
                "Owner_Name": owner_name,
                "Owner_Email": owner_email,
                "PhoneNUMB": phone_number
            }
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error adding owner: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Error adding owner: {str(e)}"
        }), 500
    finally:
        _safe_close(cursor, conn)


@mechanic_bp.route("/api/all-owners", methods=['GET'])
@mechanic_login_required
def get_all_owners():
    """Get all owners with car counts"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                o.Owner_ID, 
                o.Owner_Name, 
                o.Owner_Email, 
                o.PhoneNUMB,
                COUNT(c.Car_plate) as car_count
            FROM owner o
            LEFT JOIN car c ON o.Owner_ID = c.Owner_ID
            GROUP BY o.Owner_ID, o.Owner_Name, o.Owner_Email, o.PhoneNUMB
            ORDER BY o.Owner_Name
        """)
        
        owners = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "owners": owners,
            "count": len(owners)
        })
        
    except Exception as e:
        logger.error(f"Error getting all owners: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "Error loading owners list"
        }), 500
    finally:
        _safe_close(cursor, conn)


@mechanic_bp.route("/api/ownerless-cars", methods=['GET'])
@mechanic_login_required
def get_ownerless_cars():
    """Get all cars that don't have an owner assigned"""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                Car_plate, 
                Model, 
                Year, 
                VIN, 
                Next_Oil_Change
            FROM car 
            WHERE Owner_ID IS NULL
            ORDER BY Car_plate
        """)
        
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
        logger.error(f"Error getting ownerless cars: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "Error loading ownerless cars"
        }), 500
    finally:
        _safe_close(cursor, conn)


@mechanic_bp.route("/api/assign-car-to-owner", methods=['POST'])
@mechanic_login_required
def assign_car_to_owner():
    """Assign a car to an owner (or reassign to different owner)"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    car_plate = data.get('car_plate', '').strip().upper()
    owner_id = data.get('owner_id')
    
    # Input validation
    if not car_plate:
        return jsonify({"success": False, "message": "Car plate is required"}), 400
    
    if not re.match(r'^[A-Z]{1}[0-9]{1,6}$', car_plate):
        return jsonify({"success": False, "message": "Invalid car plate format"}), 400
    
    if not owner_id:
        return jsonify({"success": False, "message": "Owner ID is required"}), 400
    
    try:
        owner_id = int(owner_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Owner ID must be a valid number"}), 400
    
    if owner_id <= 0:
        return jsonify({"success": False, "message": "Invalid owner ID"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if car exists
        cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE Car_plate = %s", (car_plate,))
        car = cursor.fetchone()
        
        if not car:
            return jsonify({
                "success": False,
                "message": f"Car with plate {car_plate} not found"
            }), 404
        
        # Check if owner exists
        cursor.execute("SELECT Owner_ID, Owner_Name FROM owner WHERE Owner_ID = %s", (owner_id,))
        owner = cursor.fetchone()
        
        if not owner:
            return jsonify({
                "success": False,
                "message": f"Owner with ID {owner_id} not found"
            }), 404
        
        # Get current owner name if any
        current_owner_name = "No owner (ownerless)"
        if car['Owner_ID']:
            cursor.execute("SELECT Owner_Name FROM owner WHERE Owner_ID = %s", (car['Owner_ID'],))
            current_owner = cursor.fetchone()
            if current_owner:
                current_owner_name = current_owner['Owner_Name']
        
        # Assign car to new owner
        cursor.execute("""
            UPDATE car 
            SET Owner_ID = %s 
            WHERE Car_plate = %s
        """, (owner_id, car_plate))
        
        conn.commit()
        
        logger.info(f"Car {car_plate} reassigned from '{current_owner_name}' to '{owner['Owner_Name']}' (ID: {owner_id}) by {session.get('mechanic_username')}")
        
        return jsonify({
            "success": True,
            "message": f"Car {car_plate} assigned to owner '{owner['Owner_Name']}'",
            "car_plate": car_plate,
            "owner_id": owner_id,
            "owner_name": owner['Owner_Name'],
            "previous_owner": current_owner_name
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error assigning car to owner: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Error assigning car: {str(e)}"
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
    """After-service form submission - PRESERVING ALL EXISTING FUNCTIONALITY"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
        
        # Extract and validate data - EXISTING CODE PRESERVED
        plate_number = data.get('plate_number', '').strip().upper()
        service_type = data.get('service_type', '')
        mileage = data.get('mileage')
        notes = data.get('notes', '')
        next_service_date = data.get('next_service_date')  # Can be empty
        mechanic_notes = data.get('mechanic_notes', '')
        
        # Validate required fields - EXISTING CODE PRESERVED
        if not plate_number or not re.match(r'^[A-Z0-9]{4,12}$', plate_number):
            return jsonify({"success": False, "message": "Invalid plate number"}), 400
        
        if not service_type:
            return jsonify({"success": False, "message": "Service type is required"}), 400
        
        # Allow numeric strings, coerce to int - EXISTING CODE PRESERVED
        try:
            mileage = int(mileage)
        except Exception:
            return jsonify({"success": False, "message": "Valid mileage is required"}), 400

        if mileage <= 0:
            return jsonify({"success": False, "message": "Valid mileage is required"}), 400
        
        # NEW FEATURE: Auto-calculate next oil change if not provided (+3 months from today)
        # But only if it's truly empty/not provided (preserving user's choice)
        auto_calculated = False
        if next_service_date is None or (isinstance(next_service_date, str) and next_service_date.strip() == ''):
            # User didn't provide a date, so we auto-calculate
            today = datetime.now().date()
            next_service_date = add_months(today, 3)
            auto_calculated = True
            logger.info(f"Auto-calculated next oil change: {next_service_date} (+3 months)")
        else:
            # User provided a date, validate it (EXISTING VALIDATION)
            try:
                # Ensure it's a valid date format
                datetime.strptime(next_service_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    "success": False, 
                    "message": "Invalid date format. Use YYYY-MM-DD"
                }), 400
        
        # Verify car exists and user has permission - EXISTING CODE PRESERVED
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Verify car exists - EXISTING CODE PRESERVED
            cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (plate_number,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Car not found"}), 404
            
            # Insert service history - EXISTING CODE PRESERVED
            cursor.execute("""
                INSERT INTO service_history 
                (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
                VALUES (CURDATE(), %s, CURDATE(), %s, %s)
            """, (mileage, notes, plate_number))
            
            history_id = cursor.lastrowid
            
            # Update next oil change - EXISTING CODE PRESERVED (now with auto-calculated date)
            cursor.execute("""
                UPDATE car 
                SET Next_Oil_Change = %s 
                WHERE Car_plate = %s
            """, (next_service_date, plate_number))
            
            conn.commit()
            
            # NEW: Enhanced response message
            response_message = "Service record submitted successfully"
            if auto_calculated:
                response_message += f". Next oil change auto-scheduled for {next_service_date} (+3 months)"
            
            # Log the service - EXISTING CODE PRESERVED (enhanced)
            logger.info(f"Service completed for plate {plate_number} by {session.get('mechanic_username')}. History ID: {history_id}. Next oil: {next_service_date}" + 
                       (" (auto-calculated)" if auto_calculated else ""))
            
            # EXISTING RESPONSE STRUCTURE PRESERVED (with extra info added)
            return jsonify({
                "success": True,
                "message": response_message,
                "service_history_id": history_id,
                "plate_number": plate_number,
                # NEW: Additional info (optional - doesn't break existing frontend)
                "next_service_date": str(next_service_date),
                "auto_calculated": auto_calculated
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
    """Complete service with STRICT mileage validation - PRESERVING ALL EXISTING FUNCTIONALITY"""
    logger.info("Completing service with strict mileage validation")
    
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    # EXISTING CODE PRESERVED
    car_plate = data.get('car_plate', '').strip().upper()
    mileage = data.get('mileage')
    next_oil_change = data.get('next_oil_change')  # Can be empty
    notes = data.get('notes', '')
    services_performed = data.get('services_performed', [])
    
    # EXISTING VALIDATION PRESERVED
    if not car_plate:
        return jsonify({"success": False, "message": "Car plate is required"}), 400
    
    if not mileage:
        return jsonify({"success": False, "message": "Mileage is required"}), 400
    
    # Convert to integer and validate - EXISTING CODE PRESERVED
    try:
        mileage = int(mileage)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Mileage must be a valid number"}), 400
    
    if mileage <= 0:
        return jsonify({"success": False, "message": "Mileage must be greater than 0"}), 400
    
    # NEW FEATURE: Auto-calculate next oil change if empty/not provided
    auto_calculated = False
    if next_oil_change is None or (isinstance(next_oil_change, str) and next_oil_change.strip() == ''):
        # User didn't provide a date, so we auto-calculate
        today = datetime.now().date()
        next_oil_change = add_months(today, 3)
        auto_calculated = True
        logger.info(f"Auto-calculated next oil change: {next_oil_change} (+3 months)")
    else:
        # User provided a date, validate it (EXISTING VALIDATION)
        try:
            next_oil_date = datetime.strptime(next_oil_change, '%Y-%m-%d').date()
            if next_oil_date < datetime.now().date():
                return jsonify({"success": False, "message": "Next oil change date cannot be in the past"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format (use YYYY-MM-DD)"}), 400
    
    # REST OF EXISTING CODE PRESERVED EXACTLY AS IS...
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Validate car exists - EXISTING CODE
        cursor.execute("SELECT Car_plate, Year FROM car WHERE Car_plate = %s", (car_plate,))
        car = cursor.fetchone()
        
        if not car:
            return jsonify({"success": False, "message": "Car not found"}), 404
        
        # 2. Get MAXIMUM mileage for this car plate - EXISTING CODE
        cursor.execute("""
            SELECT MAX(Mileage) as max_mileage
            FROM service_history 
            WHERE Car_plate = %s
        """, (car_plate,))
        
        result = cursor.fetchone()
        max_mileage = result['max_mileage'] if result and result['max_mileage'] is not None else 0
        
        # 3. STRICT VALIDATION: Mileage must be greater than MAX recorded mileage - EXISTING CODE
        if max_mileage > 0 and mileage <= max_mileage:
            error_msg = f"New mileage ({mileage:,} km) must be GREATER than maximum recorded mileage ({max_mileage:,} km)"
            logger.warning("Mileage validation failed: %s", error_msg)
            return jsonify({
                "success": False, 
                "message": error_msg
            }), 400
        
        # 4. Additional validation: Check for unrealistic mileage jump - EXISTING CODE
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
        
        # 5. Validate reasonable mileage based on car age - EXISTING CODE
        car_year = car['Year'] or datetime.now().year
        current_year = datetime.now().year
        car_age = current_year - car_year
        
        # Reasonable maximum: 25,000 km per year + 50,000 base
        reasonable_max = car_age * 25000 + 50000
        
        if mileage > reasonable_max:
            warning_msg = f"High mileage for {car_year} vehicle: {mileage:,} km (expected max: {reasonable_max:,} km)"
            logger.warning(warning_msg)
        
        # 6. Create service history record - EXISTING CODE
        service_date = datetime.now().date()
        
        cursor.execute("""
            INSERT INTO service_history (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
            VALUES (%s, %s, CURDATE(), %s, %s)
        """, (service_date, mileage, notes, car_plate))
        
        history_id = cursor.lastrowid
        logger.info("Created service history record #%s with mileage %s", history_id, mileage)
        
        # 7. Link services performed (validate IDs) - EXISTING CODE
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
        
        # 8. Update next oil change - EXISTING CODE (now with auto-calculated date if needed)
        cursor.execute("""
            UPDATE car 
            SET Next_Oil_Change = %s 
            WHERE Car_plate = %s
        """, (next_oil_change, car_plate))
        logger.info("Updated next oil change to %s for %s", next_oil_change, car_plate)
        
        conn.commit()
        
        # Log the service completion - EXISTING CODE (enhanced)
        logger.info(f"Service completed for {car_plate} - Mileage: {mileage:,} km (previous max: {max_mileage:,} km) by {session.get('mechanic_username')}" +
                   f". Next oil: {next_oil_change}" + (" (auto-calculated)" if auto_calculated else ""))
        
        # EXISTING RESPONSE STRUCTURE PRESERVED (with extra info added)
        return jsonify({
            "success": True,
            "message": f"Service completed successfully for {car_plate}. Mileage updated from {max_mileage:,} km to {mileage:,} km." +
                      (f" Next oil change auto-scheduled for {next_oil_change} (+3 months)." if auto_calculated else ""),
            "service_history_id": history_id,
            "mileage_recorded": mileage,
            "previous_max_mileage": max_mileage,
            # NEW: Additional info (optional - doesn't break existing frontend)
            "next_oil_change": str(next_oil_change),
            "auto_calculated": auto_calculated
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
        
        # Get service history with car and owner info, including service types
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
                o.Owner_Email as Email,
                IF(GROUP_CONCAT(s.Service_Type SEPARATOR ', ') IS NULL OR GROUP_CONCAT(s.Service_Type SEPARATOR ', ') = '', 'Maintenance', GROUP_CONCAT(s.Service_Type SEPARATOR ', ')) as Service_Type
            FROM service_history sh
            LEFT JOIN car c ON sh.Car_plate = c.Car_plate
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
            LEFT JOIN service_history_service shs ON sh.History_ID = shs.History_ID
            LEFT JOIN service s ON shs.Service_ID = s.Service_ID
            GROUP BY sh.History_ID
            ORDER BY sh.Service_Date DESC
        """)
        
        services = cursor.fetchall()
        
        # Format dates for frontend
        for service in services:
            if service['Service_Date'] and hasattr(service['Service_Date'], 'isoformat'):
                service['Service_Date'] = service['Service_Date'].isoformat()
        
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
    """Get owner information by ID - with validation and better error handling"""
    if not isinstance(owner_id, int) or owner_id <= 0:
        return jsonify({
            "success": False,
            "message": "Invalid owner ID"
        }), 400
    
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
            "message": "Database error retrieving owner information"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/owner/<int:owner_id>", methods=['PUT'])
@mechanic_login_required
def update_owner(owner_id):
    """Update owner information with comprehensive validation"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    owner_name = data.get('owner_name', '').strip()
    owner_email = data.get('owner_email', '').strip()
    phone_number = data.get('phone_number', '').strip()
    
    # Validation with better error messages
    if not owner_name:
        return jsonify({"success": False, "message": "Owner name is required"}), 400
    
    if len(owner_name) > 100:
        return jsonify({"success": False, "message": "Owner name is too long"}), 400
    
    if not phone_number:
        return jsonify({"success": False, "message": "Phone number is required"}), 400
    
    if len(phone_number) > 20:
        return jsonify({"success": False, "message": "Phone number is too long"}), 400
    
    # Basic email validation (optional field)
    if owner_email:
        if '@' not in owner_email or len(owner_email) > 100:
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
            "message": "Error updating owner information"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/car/<car_plate>", methods=['PUT'])
@mechanic_login_required
def update_car(car_plate):
    """Update car information with comprehensive validation"""
    car_plate = car_plate.strip().upper()
    
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
    
    if len(model) > 100:
        return jsonify({"success": False, "message": "Car model name is too long"}), 400
    
    # Type coercion for year
    try:
        year = int(year) if year else None
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Year must be a valid number"}), 400
    
    if not year or year < 1900 or year > datetime.now().year + 1:
        return jsonify({"success": False, "message": f"Valid manufacturing year required (1900-{datetime.now().year + 1})"}), 400
    
    if not vin or len(vin) != 17:
        return jsonify({"success": False, "message": "Valid 17-character VIN is required"}), 400
    
    if next_oil_change:
        try:
            next_oil_date = datetime.strptime(next_oil_change, '%Y-%m-%d').date()
            if next_oil_date < datetime.now().date():
                return jsonify({"success": False, "message": "Next oil change date cannot be in the past"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format (use YYYY-MM-DD)"}), 400
    
    # Validate owner_id if provided
    if owner_id:
        try:
            owner_id = int(owner_id)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Invalid owner ID"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if car exists and fetch current owner
        cursor.execute("SELECT Car_plate, Owner_ID FROM car WHERE Car_plate = %s", (car_plate,))
        car_row = cursor.fetchone()
        if not car_row:
            return jsonify({"success": False, "message": f"Car with plate {car_plate} not found"}), 404

        current_owner_id = car_row.get('Owner_ID') if car_row else None

        # If owner_id provided, validate it and use it; otherwise keep existing owner if present
        final_owner_id = None
        if owner_id is not None:
            try:
                owner_id = int(owner_id)
            except (ValueError, TypeError):
                return jsonify({"success": False, "message": "Invalid owner ID"}), 400

            cursor.execute("SELECT Owner_ID FROM owner WHERE Owner_ID = %s", (owner_id,))
            if not cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": f"Owner with ID {owner_id} not found. Please create the owner first (use the Owners UI or Add Owner flow) before assigning this car."
                }), 404

            final_owner_id = owner_id
        else:
            # owner omitted in request — preserve existing owner if any
            if current_owner_id:
                final_owner_id = current_owner_id
            else:
                return jsonify({"success": False, "message": "Owner is required for this car. Please provide an owner_id."}), 400

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

        # Update car information (use final_owner_id to preserve existing owner when omitted)
        cursor.execute("""
            UPDATE car 
            SET Model = %s, 
                Year = %s, 
                VIN = %s, 
                Next_Oil_Change = %s,
                Owner_ID = %s
            WHERE Car_plate = %s
        """, (model, year, vin, next_oil_change, final_owner_id, car_plate))
        
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
            "message": "Error updating car information"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/search-owners", methods=['GET'])
@mechanic_login_required
def search_owners():
    """Search owners by name, email, or phone with better error handling"""
    search_term = request.args.get('q', '').strip()
    
    if not search_term or len(search_term) < 2:
        return jsonify({"success": False, "message": "Please enter at least 2 characters"}), 400
    
    if len(search_term) > 100:
        return jsonify({"success": False, "message": "Search term too long"}), 400
    
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
            "message": "Error searching owners"
        }), 500
    finally:
        _safe_close(cursor, conn)

@mechanic_bp.route("/api/search-cars", methods=['GET'])
@mechanic_login_required
def search_cars():
    """Search cars by plate, VIN, or owner with improved query"""
    search_term = request.args.get('q', '').strip()
    search_by = request.args.get('type', 'plate').strip().lower()  # plate, vin, owner
    
    if not search_term or len(search_term) < 2:
        return jsonify({"success": False, "message": "Please enter at least 2 characters"}), 400
    
    if len(search_term) > 100:
        return jsonify({"success": False, "message": "Search term too long"}), 400
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        search_pattern = f"%{search_term}%"
        
        if search_by == 'vin':
            cursor.execute("""
                SELECT 
                    c.Car_plate,
                    c.Model,
                    c.Year,
                    c.VIN,
                    c.Owner_ID,
                    c.Next_Oil_Change,
                    o.Owner_Name,
                    o.Owner_Email,
                    o.PhoneNUMB
                FROM car c
                LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
                WHERE UPPER(c.VIN) LIKE UPPER(%s)
                ORDER BY c.Car_plate
                LIMIT 20
            """, (search_pattern,))
        elif search_by == 'owner':
            cursor.execute("""
                SELECT 
                    c.Car_plate,
                    c.Model,
                    c.Year,
                    c.VIN,
                    c.Owner_ID,
                    c.Next_Oil_Change,
                    o.Owner_Name,
                    o.Owner_Email,
                    o.PhoneNUMB
                FROM car c
                LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
                WHERE o.Owner_Name LIKE %s
                   OR o.Owner_Email LIKE %s
                   OR o.PhoneNUMB LIKE %s
                ORDER BY c.Car_plate
                LIMIT 20
            """, (search_pattern, search_pattern, search_pattern))
        else:  # default: plate
            cursor.execute("""
                SELECT 
                    c.Car_plate,
                    c.Model,
                    c.Year,
                    c.VIN,
                    c.Owner_ID,
                    c.Next_Oil_Change,
                    o.Owner_Name,
                    o.Owner_Email,
                    o.PhoneNUMB
                FROM car c
                LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
                WHERE UPPER(c.Car_plate) LIKE UPPER(%s)
                ORDER BY c.Car_plate
                LIMIT 20
            """, (search_pattern,))
        
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
        logger.error(f"Error searching cars: {e}")
        return jsonify({
            "success": False,
            "message": "Error searching cars"
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