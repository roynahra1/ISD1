from flask import Blueprint, request, jsonify
import logging
from utils.database import get_connection, _safe_close

owner_bp = Blueprint('owners', __name__)

@owner_bp.route("/owners", methods=["GET"])
def get_owners():
    """Get all owners"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT Owner_ID, Owner_Name as name, Owner_Email, PhoneNUMB FROM owner")
        owners = cursor.fetchall()
        return jsonify(owners)
    except Exception as err:
        logging.error(f"Fetch owners failed: {err}")
        return jsonify([]), 500
    finally:
        _safe_close(cursor, conn)

@owner_bp.route("/owners/add", methods=["POST"])
def add_owner():
    """Add new owner"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        
        if not all([name, phone]):
            return jsonify({"success": False, "message": "Name and phone are required"}), 400
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if owner already exists
        cursor.execute("SELECT Owner_ID FROM owner WHERE PhoneNUMB = %s", (phone,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Owner with this phone already exists"}), 400
        
        cursor.execute(
            "INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB) VALUES (%s, %s, %s)",
            (name, email, phone)
        )
        
        conn.commit()
        return jsonify({"success": True, "message": "Owner added successfully", "owner_id": cursor.lastrowid})
        
    except Exception as e:
        logging.error(f"Add owner error: {e}")
        return jsonify({"success": False, "message": "Failed to add owner"}), 500
    finally:
        _safe_close(cursor, conn)