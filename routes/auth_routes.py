from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from mysql.connector import Error

from utils.database import get_connection, _safe_close

auth_bp = Blueprint('auth', __name__)

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
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(err)}), 500
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
            session["logged_in"] = True
            session["username"] = username
            session.permanent = True
            return jsonify({"status": "success", "message": "Login successful"}), 200

        return jsonify({"status": "error", "message": "Invalid username or password"}), 401

    except Error as err:
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out"}), 200

@auth_bp.route("/auth/status", methods=["GET"])
def auth_status():
    return jsonify({
        "status": "success",
        "logged_in": bool(session.get("logged_in")),
        "username": session.get("username")
    })