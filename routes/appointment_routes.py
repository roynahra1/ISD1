from flask import Blueprint, request, jsonify, session, redirect, render_template
from datetime import datetime
from mysql.connector import Error
from utils.database import get_connection, _safe_close
from utils.helpers import serialize

appointment_bp = Blueprint('appointments', __name__)

# Template routes
@appointment_bp.route("/appointment.html")
def serve_form():
    return render_template("appointment.html")

@appointment_bp.route("/viewAppointment/search")
def serve_view():
    return render_template("viewAppointment.html")

@appointment_bp.route("/updateAppointment.html")
def serve_update():
    if not session.get("logged_in"):
        return redirect("/login.html")
    if not session.get("selected_appointment"):
        return redirect("/viewAppointment/search")
    return render_template("updateAppointment.html")

# Appointment CRUD routes
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
            conn.rollback()
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

@appointment_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
def get_appointment_by_id(appointment_id: int):
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
            WHERE a.Appointment_id = %s
            GROUP BY a.Appointment_id
            """,
            (appointment_id,),
        )
        appointment = cursor.fetchone()
        if not appointment:
            return jsonify({"status": "error", "message": "Appointment not found"}), 404
        for k, v in appointment.items():
            appointment[k] = serialize(v)
        return jsonify({"status": "success", "appointment": appointment}), 200
    except Error as err:
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointments/select", methods=["POST"])
def select_appointment():
    # Check login status first
    if not session.get("logged_in"):
        return jsonify({
            "status": "error",
            "message": "Please login first"
        }), 401

    data = request.get_json() or {}
    appointment_id = data.get("appointment_id")
    
    if not appointment_id:
        return jsonify({"status": "error", "message": "Missing appointment ID"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT a.*, GROUP_CONCAT(s.Service_Type) as Services,
                   GROUP_CONCAT(s.Service_ID) as service_ids
            FROM appointment a
            LEFT JOIN appointment_service aps ON a.Appointment_id = aps.Appointment_id
            LEFT JOIN service s ON aps.Service_ID = s.Service_ID
            WHERE a.Appointment_id = %s
            GROUP BY a.Appointment_id
        """, (appointment_id,))
        
        appointment = cursor.fetchone()
        
        if not appointment:
            return jsonify({"status": "error", "message": "Appointment not found"}), 404

        # Store in session
        session['selected_appointment_id'] = appointment_id
        session['selected_appointment'] = {k: serialize(v) for k, v in appointment.items()}
        
        return jsonify({
            "status": "success",
            "message": "Appointment selected"
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointments/current", methods=["GET"])
def get_current_appointment():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    appointment = session.get("selected_appointment")
    if not appointment:
        return jsonify({"status": "error", "message": "No appointment selected"}), 404
        
    return jsonify({
        "status": "success",
        "appointment": appointment
    })

@appointment_bp.route("/appointments/update", methods=["PUT"])
def update_selected_appointment():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    # Get appointment ID from session
    appointment_id = session.get("selected_appointment_id")
    if not appointment_id:
        return jsonify({"status": "error", "message": "No appointment selected"}), 400

    data = request.get_json() or {}
    date = data.get("date")
    time = data.get("time")
    
    # Validate date/time not in past
    try:
        date_time_str = f"{date} {time}"
        appointment_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
        if appointment_datetime < datetime.now():
            return jsonify({
                "status": "error",
                "message": "Cannot set appointment date/time in the past"
            }), 400
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "Invalid date/time format"
        }), 400

    notes = data.get("notes", "")
    service_ids = data.get("service_ids", [])

    if not date or not time:
        return jsonify({"status": "error", "message": "Missing date or time"}), 400

    # validate date/time format
    try:
        datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid date/time format"}), 400

    if not isinstance(service_ids, list):
        return jsonify({"status": "error", "message": "service_ids must be a list"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        # ensure appointment exists
        cursor.execute("SELECT 1 FROM appointment WHERE Appointment_id = %s", (appointment_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"status": "error", "message": "Appointment not found"}), 404

        # check for time conflict (exclude current appointment)
        cursor.execute(
            "SELECT COUNT(*) FROM appointment WHERE Date = %s AND Time = %s AND Appointment_id != %s",
            (date, time, appointment_id),
        )
        if cursor.fetchone()[0] > 0:
            conn.rollback()
            return jsonify({"status": "error", "message": "Time slot already booked"}), 409

        # update appointment
        cursor.execute(
            "UPDATE appointment SET Date = %s, Time = %s, Notes = %s WHERE Appointment_id = %s",
            (date, time, notes, appointment_id),
        )

        # replace services: delete existing then insert provided ones (validate ids)
        cursor.execute("DELETE FROM appointment_service WHERE Appointment_id = %s", (appointment_id,))
        if service_ids:
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

        # fetch updated appointment
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT a.Appointment_id, a.Date, a.Time, a.Notes, a.Car_plate,
                   GROUP_CONCAT(s.Service_Type) AS Services
            FROM appointment a
            LEFT JOIN appointment_service aps ON a.Appointment_id = aps.Appointment_id
            LEFT JOIN service s ON aps.Service_ID = s.Service_ID
            WHERE a.Appointment_id = %s
            GROUP BY a.Appointment_id
            """,
            (appointment_id,),
        )
        updated = cursor.fetchone()
        if not updated:
            return jsonify({"status": "error", "message": "Appointment not found after update"}), 404
        for k, v in updated.items():
            updated[k] = serialize(v)
        updated["Services"] = updated.get("Services") or ""
        return jsonify({"status": "success", "message": "Appointment updated", "appointment": updated}), 200

    except Error as err:
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointments/<int:appointment_id>", methods=["DELETE"])
def delete_appointment(appointment_id: int):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM appointment_service WHERE Appointment_id = %s", (appointment_id,))
        cursor.execute("DELETE FROM appointment WHERE Appointment_id = %s", (appointment_id,))
        conn.commit()
        return jsonify({"status": "success", "message": "Appointment deleted"}), 200
    except Error as err:
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(err)}), 500
    finally:
        _safe_close(cursor, conn)