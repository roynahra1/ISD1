from flask import Blueprint, request, jsonify, session, render_template
from werkzeug.security import check_password_hash, generate_password_hash
from mysql.connector import Error
import logging
from utils.database import get_connection, _safe_close
from utils.helpers import serialize

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ===============================
# EXISTING TEMPLATE ROUTES (UNCHANGED)
# ===============================

@auth_bp.route("/login.html")
def login_page():
    return render_template("login.html")

@auth_bp.route("/signup.html")
def signup_page():
    return render_template("signup.html")

@auth_bp.route("/mechanic/login.html")
def mechanic_login_page():
    """Serve mechanic login page"""
    return render_template("mechanic_login.html")

@auth_bp.route("/admin/login.html")
def admin_login_page():
    """Serve admin login page"""
    return render_template("admin_login.html")

# ===============================
# EXISTING AUTHENTICATION ROUTES (UNCHANGED)
# ===============================

@auth_bp.route("/signup", methods=["POST"])
def signup():
    """
    Create both user account (admin table) and owner record in one step
    """
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    owner_name = (data.get("owner_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone_number = (data.get("phone_number") or "").strip()

    # Validate all required fields
    if not username or not password or not owner_name or not email:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        conn.start_transaction()  # Start transaction

        # ============================================
        # 1. VALIDATE UNIQUENESS
        # ============================================
        # Check if username exists
        cursor.execute("SELECT 1 FROM admin WHERE Username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Username already exists"}), 409

        # Check if email exists in admin table (as username email)
        cursor.execute("SELECT 1 FROM admin WHERE Email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Email already registered"}), 409

        # Check if email exists in owner table
        cursor.execute("SELECT 1 FROM owner WHERE Owner_Email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Email already used by another owner"}), 409

        # Check if phone exists in owner table (if provided)
        if phone_number:
            cursor.execute("SELECT 1 FROM owner WHERE PhoneNUMB = %s", (phone_number,))
            if cursor.fetchone():
                return jsonify({"status": "error", "message": "Phone number already registered"}), 409

        # ============================================
        # 2. CREATE OWNER RECORD FIRST
        # ============================================
        cursor.execute(
            "INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB) VALUES (%s, %s, %s)",
            (owner_name, email, phone_number if phone_number else None)
        )
        
        owner_id = cursor.lastrowid  # Get the new owner's ID
        print(f"✅ Created owner record: ID={owner_id}, Name={owner_name}, Email={email}")

        # ============================================
        # 3. CREATE USER ACCOUNT (LINKED TO OWNER)
        # ============================================
        hashed = generate_password_hash(password)
        
        cursor.execute(
            "INSERT INTO admin (Username, Email, Password, PhoneNUMB, Owner_ID) VALUES (%s, %s, %s, %s, %s)",
            (username, email, hashed, phone_number if phone_number else None, owner_id)
        )
        
        user_id = cursor.lastrowid
        print(f"✅ Created user account: ID={user_id}, Username={username}, Owner_ID={owner_id}")

        conn.commit()  # Commit transaction
        
        return jsonify({
            "status": "success", 
            "message": "Account and owner profile created successfully",
            "owner_id": owner_id,
            "owner_name": owner_name,
            "username": username
        }), 201

    except Error as err:
        logger.error(f"Database error in signup: {err}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in signup: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"status": "error", "message": "Missing username or password"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)  # Use dictionary cursor!
        
        # CRITICAL: Get ALL user info including Owner_ID
        cursor.execute("""
            SELECT a.Username, a.Password, a.Email, a.PhoneNUMB, a.Owner_ID,
                   o.Owner_Name, o.Owner_Email, o.PhoneNUMB as Owner_Phone
            FROM admin a
            LEFT JOIN owner o ON a.Owner_ID = o.Owner_ID
            WHERE a.Username = %s
        """, (username,))
        
        user = cursor.fetchone()
        
        if user and check_password_hash(user['Password'], password):
            # ✅ Set session with ALL user data including Owner_ID
            session.clear()
            session["logged_in"] = True
            session["username"] = user['Username']
            session["email"] = user['Email']
            session["phone"] = user['PhoneNUMB']
            session.permanent = True

            # Only set owner_id if the owner record actually exists
            owner_id = user.get('Owner_ID')
            if owner_id:
                cursor.execute("SELECT 1 FROM owner WHERE Owner_ID = %s", (owner_id,))
                if cursor.fetchone():
                    session["owner_id"] = owner_id
                    session["owner_name"] = user.get('Owner_Name')
                    session["owner_email"] = user.get('Owner_Email')
                    session["owner_phone"] = user.get('Owner_Phone')
                else:
                    # Owner_ID stored in admin table points to a missing owner — treat as unlinked
                    logger.warning(f"Admin account {username} has invalid Owner_ID={owner_id}; treating as unlinked")
            # If owner_id is None or invalid, session will not contain owner fields
            
            print(f"✅ Login successful: {username}, Owner_ID={session.get('owner_id')}")

            return jsonify({
                "status": "success",
                "message": "Login successful",
                "owner_id": session.get('owner_id'),
                "owner_name": session.get('owner_name'),
                "has_owner_linked": session.get('owner_id') is not None
            }), 200

        return jsonify({"status": "error", "message": "Invalid username or password"}), 401

    except Error as err:
        logger.error(f"Database error in login: {err}")
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in login: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/owner/link", methods=["POST"])
def link_owner():
    # Require logged in
    if not session.get("logged_in"):
        return jsonify({"status":"error","message":"Please login first"}), 401

    data = request.get_json() or {}
    owner_name = (data.get("owner_name") or "").strip()
    owner_email = (data.get("owner_email") or "").strip()
    owner_phone = (data.get("owner_phone") or "").strip()

    if not owner_name or not owner_email:
        return jsonify({"status":"error","message":"Missing owner details"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        # Create owner record
        cursor.execute(
            "INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB) VALUES (%s, %s, %s)",
            (owner_name, owner_email, owner_phone if owner_phone else None)
        )
        new_owner_id = cursor.lastrowid

        # Link admin row for current user
        username = session.get("username")
        cursor.execute("UPDATE admin SET Owner_ID = %s WHERE Username = %s", (new_owner_id, username))

        conn.commit()

        # Update session with owner info
        session["owner_id"] = new_owner_id
        session["owner_name"] = owner_name
        session["owner_email"] = owner_email
        session["owner_phone"] = owner_phone

        return jsonify({"status":"success","message":"Owner profile linked","owner_id":new_owner_id}), 200

    except Error as err:
        if conn:
            conn.rollback()
        logger.error(f"Database error linking owner: {err}")
        return jsonify({"status":"error","message":"Database error"}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error linking owner: {e}")
        return jsonify({"status":"error","message":"Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)
@auth_bp.route("/logout", methods=["POST"])
def logout():
    try:
        session.clear()
        return jsonify({"status": "success", "message": "Logged out"}), 200
    except Exception as e:
        logger.error(f"Error in logout: {e}")
        return jsonify({"status": "error", "message": "Logout failed"}), 500

@auth_bp.route("/auth/status", methods=["GET"])
def auth_status():
    try:
        owner_info = None
        if session.get("owner_id"):
            owner_info = {
                "owner_id": session.get("owner_id"),
                "owner_name": session.get("owner_name"),
                "owner_email": session.get("owner_email"),
                "owner_phone": session.get("owner_phone")
            }
        
        return jsonify({
            "status": "success",
            "logged_in": bool(session.get("logged_in")),
            "username": session.get("username"),
            "email": session.get("email"),
            "phone": session.get("phone"),
            "owner_info": owner_info,
            "has_owner_linked": session.get("owner_id") is not None
        })
    except Exception as e:
        logger.error(f"Error in auth_status: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
# ===============================
# MECHANIC-SPECIFIC AUTHENTICATION (NEW SESSION KEYS)
# ===============================

@auth_bp.route("/mechanic/login", methods=["POST"])
def mechanic_login():
    """Mechanic login endpoint - uses separate session keys"""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    print(f"🔧 Mechanic login attempt - Username: {username}")

    if not username or not password:
        return jsonify({"status": "error", "message": "Missing username or password"}), 400

    # Check against admin table in database
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT Username, Password FROM admin WHERE Username = %s", (username,))
        user = cursor.fetchone()
        
        if user:
            # ✅ FIX: Clear session first to remove any existing regular session
            session.clear()
            
            # Use MECHANIC-specific session keys
            session["mechanic_logged_in"] = True
            session["mechanic_username"] = username
            session["mechanic_user_type"] = "admin" if username == "admin" else "mechanic"
            session.permanent = True
            
            print(f"✅ Mechanic login SUCCESS: {username}")
            print(f"✅ Session cleared and mechanic session set")
            
            redirect_url = "/mechanic/admin/dashboard" if username == "admin" else "/mechanic/dashboard"
            return jsonify({
                "status": "success", 
                "message": "Mechanic login successful",
                "redirect": redirect_url
            }), 200
        else:
            # Fallback to demo accounts
            user_credentials = {
                'mechanic1': '12345',
                'john_tech': 'password123',
                'mechanic': 'password',
                'admin': 'admin123'
            }
            
            if username in user_credentials and password == user_credentials[username]:
                # ✅ FIX: Clear session first to remove any existing regular session
                session.clear()
                
                # Use MECHANIC-specific session keys
                session["mechanic_logged_in"] = True
                session["mechanic_username"] = username
                session["mechanic_user_type"] = "admin" if username == "admin" else "mechanic"
                session.permanent = True
                
                print(f"✅ Mechanic login SUCCESS (demo): {username}")
                print(f"✅ Session cleared and mechanic session set")
                
                redirect_url = "/mechanic/admin/dashboard" if username == "admin" else "/mechanic/dashboard"
                return jsonify({
                    "status": "success", 
                    "message": "Mechanic login successful",
                    "redirect": redirect_url
                }), 200

        print(f"❌ Mechanic login FAILED: Invalid credentials for {username}")
        return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        
    except Exception as e:
        logger.error(f"Mechanic login error: {e}")
        return jsonify({"status": "error", "message": "Database error during login"}), 500
    finally:
        _safe_close(cursor, conn)
        
@auth_bp.route("/admin/login", methods=["POST"])
def admin_login():
    """Admin login endpoint - uses mechanic session keys"""
    return mechanic_login()

@auth_bp.route("/mechanic/logout", methods=["POST"])
def mechanic_logout():
    """Mechanic logout - only clears mechanic session keys"""
    try:
        username = session.get("mechanic_username", "Unknown")
        # Only clear mechanic-specific session keys, preserve other sessions
        session.pop("mechanic_logged_in", None)
        session.pop("mechanic_username", None)
        session.pop("mechanic_user_type", None)
        print(f"🔧 Mechanic logged out: {username}")
        return jsonify({"status": "success", "message": "Logged out"}), 200
    except Exception as e:
        logger.error(f"Error in mechanic logout: {e}")
        return jsonify({"status": "error", "message": "Logout failed"}), 500

@auth_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    """Admin logout - uses same as mechanic logout"""
    return mechanic_logout()

@auth_bp.route("/mechanic/status", methods=["GET"])
def mechanic_auth_status():
    """Check mechanic authentication status using mechanic session keys"""
    try:
        is_logged_in = bool(session.get("mechanic_logged_in"))
        return jsonify({
            "status": "success",
            "logged_in": is_logged_in,
            "username": session.get("mechanic_username"),
            "user_type": session.get("mechanic_user_type")
        })
    except Exception as e:
        logger.error(f"Error in mechanic status check: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@auth_bp.route("/admin/status", methods=["GET"])
def admin_auth_status():
    """Check admin authentication status"""
    return mechanic_auth_status()

@auth_bp.route("/booking/create", methods=["POST"])
def create_booking():
    """
    Create a new booking
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    service_id = data.get("service_id")
    date = data.get("date")
    time = data.get("time")
    notes = data.get("notes", "")

    # Validate input
    if not service_id or not date or not time:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if owner_id is linked
        owner_id = session.get("owner_id")
        if not owner_id:
            return jsonify({
                "status": "error",
                "message": "Your account is not linked to an owner profile. Please link an owner profile before booking.",
                "link_endpoint": "/owner/link"
            }), 400

        # Create booking
        cursor.execute(
            "INSERT INTO bookings (Service_ID, Owner_ID, Date, Time, Notes) VALUES (%s, %s, %s, %s, %s)",
            (service_id, owner_id, date, time, notes)
        )
        booking_id = cursor.lastrowid

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Booking created successfully",
            "booking_id": booking_id
        }), 201

    except Error as err:
        logger.error(f"Database error creating booking: {err}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error creating booking: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/bookings", methods=["GET"])
def list_bookings():
    """
    List all bookings for the logged-in user
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if owner_id is linked
        owner_id = session.get("owner_id")
        if not owner_id:
            return jsonify({
                "status": "error",
                "message": "Your account is not linked to an owner profile. Please link an owner profile before viewing bookings.",
                "link_endpoint": "/owner/link"
            }), 400

        # Fetch bookings
        cursor.execute(
            "SELECT b.Booking_ID, b.Date, b.Time, b.Notes, s.Service_Name, s.Price "
            "FROM bookings b "
            "JOIN services s ON b.Service_ID = s.Service_ID "
            "WHERE b.Owner_ID = %s "
            "ORDER BY b.Date DESC, b.Time DESC",
            (owner_id,)
        )
        bookings = cursor.fetchall()

        return jsonify({
            "status": "success",
            "bookings": bookings
        }), 200

    except Error as err:
        logger.error(f"Database error fetching bookings: {err}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching bookings: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/booking/<int:booking_id>", methods=["GET"])
def get_booking(booking_id):
    """
    Get details of a specific booking
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if owner_id is linked
        owner_id = session.get("owner_id")
        if not owner_id:
            return jsonify({
                "status": "error",
                "message": "Your account is not linked to an owner profile. Please link an owner profile before viewing bookings.",
                "link_endpoint": "/owner/link"
            }), 400

        # Fetch booking details
        cursor.execute(
            "SELECT b.Booking_ID, b.Date, b.Time, b.Notes, s.Service_Name, s.Price "
            "FROM bookings b "
            "JOIN services s ON b.Service_ID = s.Service_ID "
            "WHERE b.Booking_ID = %s AND b.Owner_ID = %s",
            (booking_id, owner_id)
        )
        booking = cursor.fetchone()

        if not booking:
            return jsonify({"status": "error", "message": "Booking not found"}), 404

        return jsonify({
            "status": "success",
            "booking": booking
        }), 200

    except Error as err:
        logger.error(f"Database error fetching booking: {err}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching booking: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/booking/<int:booking_id>", methods=["PUT"])
def update_booking(booking_id):
    """
    Update an existing booking
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.get_json() or {}
    date = data.get("date")
    time = data.get("time")
    notes = data.get("notes", "")

    # Validate input
    if not date or not time:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if owner_id is linked
        owner_id = session.get("owner_id")
        if not owner_id:
            return jsonify({
                "status": "error",
                "message": "Your account is not linked to an owner profile. Please link an owner profile before updating bookings.",
                "link_endpoint": "/owner/link"
            }), 400

        # Update booking
        cursor.execute(
            "UPDATE bookings SET Date = %s, Time = %s, Notes = %s "
            "WHERE Booking_ID = %s AND Owner_ID = %s",
            (date, time, notes, booking_id, owner_id)
        )

        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Booking not found or not authorized"}), 404

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Booking updated successfully"
        }), 200

    except Error as err:
        logger.error(f"Database error updating booking: {err}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error updating booking: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/booking/<int:booking_id>", methods=["DELETE"])
def delete_booking(booking_id):
    """
    Delete a booking
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if owner_id is linked
        owner_id = session.get("owner_id")
        if not owner_id:
            return jsonify({
                "status": "error",
                "message": "Your account is not linked to an owner profile. Please link an owner profile before deleting bookings.",
                "link_endpoint": "/owner/link"
            }), 400

        # Delete booking
        cursor.execute(
            "DELETE FROM bookings WHERE Booking_ID = %s AND Owner_ID = %s",
            (booking_id, owner_id)
        )

        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "Booking not found or not authorized"}), 404

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Booking deleted successfully"
        }), 200

    except Error as err:
        logger.error(f"Database error deleting booking: {err}")
        return jsonify({"status": "error", "message": "Database error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting booking: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)