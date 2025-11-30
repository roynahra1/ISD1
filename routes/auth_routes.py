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
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400
    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password too short"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM admin WHERE Username = %s", (username,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Username already exists"}), 409

        cursor.execute("SELECT 1 FROM admin WHERE Email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Email already registered"}), 409

        hashed = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO admin (Username, Email, Password) VALUES (%s, %s, %s)",
            (username, email, hashed),
        )
        conn.commit()

        return jsonify({"status": "success", "message": "Account created"}), 201

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
        cursor = conn.cursor()
        cursor.execute("SELECT Password FROM admin WHERE Username = %s", (username,))
        row = cursor.fetchone()
        stored = row[0] if row else None

        if stored and check_password_hash(stored, password):
            session.clear()
            # ONLY set regular session keys - NO mechanic keys
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            return jsonify({"status": "success", "message": "Login successful"}), 200

        return jsonify({"status": "error", "message": "Invalid username or password"}), 401

    except Error as err:
        logger.error(f"Database error in login: {err}")
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in login: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
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
        return jsonify({
            "status": "success",
            "logged_in": bool(session.get("logged_in")),
            "username": session.get("username")
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