from flask import Blueprint, request, jsonify, session
from datetime import datetime
from mysql.connector import Error

from utils.database import get_connection, _safe_close
from utils.helpers import serialize

appointment_bp = Blueprint('appointments', __name__)

@appointment_bp.route("/book", methods=["POST"])
def book_appointment():
    data = request.get_json() or {}
    car_plate = (data.get("car_plate") or "").strip()
    date = data.get("date")
    time = data.get("time")
    service_ids = data.get("service_ids", [])
    notes = data.get("notes", "")

    if not car_plate or not date or not time or not service_ids:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    if not isinstance(service_ids, list):
        return jsonify({"status": "error", "message": "service_ids must be a list"}), 400

    try:
        requested_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid date/time format"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        if requested_dt < datetime.now():
            conn.rollback()
            return jsonify({"status": "error", "message": "Cannot book an appointment in the past"}), 400

        cursor.execute("SELECT 1 FROM appointment WHERE Date = %s AND Time = %s", (date, time))
        if cursor.fetchone():
            conn.rollback()
            return jsonify({"status": "error", "message": "Time slot already booked"}), 409

        cursor.execute("SELECT 1 FROM car WHERE Car_plate = %s", (car_plate,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_id) VALUES (%s,%s,%s,%s,%s,%s)",
                (car_plate, "Unknown", 2020, "VIN-UNKNOWN", None, 1),
            )

        cursor.execute(
            "INSERT INTO appointment (Date, Time, Notes, Car_plate) VALUES (%s, %s, %s, %s)",
            (date, time, notes, car_plate),
        )
        appointment_id = cursor.lastrowid

        cursor.execute("SELECT Service_ID FROM service")
        valid_ids = {row[0] for row in cursor.fetchall()}
        invalid = [sid for sid in service_ids if sid not in valid_ids]
        if invalid:
            conn.rollback()
            return jsonify({"status": "error", "message": f"Invalid Service_ID(s): {invalid}"}), 400

        for sid in service_ids:
            cursor.execute(
                "INSERT INTO appointment_service (Appointment_id, Service_ID) VALUES (%s, %s)",
                (appointment_id, sid),
            )

        conn.commit()
        return jsonify(
            {"status": "success", "message": f"Appointment booked for {car_plate} on {date} at {time}", "appointment_id": appointment_id}
        ), 201
    except Error as err:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointment/search", methods=["GET"])
def search_appointments_by_plate():
    car_plate = request.args.get("car_plate")
    if not car_plate:
        return jsonify({"status": "error", "message": "Missing car_plate"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.Appointment_id, a.Date, a.Time, a.Notes, a.Car_plate,
                   GROUP_CONCAT(s.Service_Type) AS Services
            FROM appointment a
            LEFT JOIN appointment_service aps ON a.Appointment_id = aps.Appointment_id
            LEFT JOIN service s ON aps.Service_ID = s.Service_ID
            WHERE a.Car_plate = %s
            GROUP BY a.Appointment_id
            ORDER BY a.Date, a.Time
            """,
            (car_plate,),
        )
        appointments = cursor.fetchall()
        for appt in appointments:
            for k, v in appt.items():
                appt[k] = serialize(v)
        return jsonify({"status": "success", "appointments": appointments}), 200
    except Error as err:
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)

# Add other appointment routes as needed...