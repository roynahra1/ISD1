from flask import Blueprint, request, jsonify, session, redirect, render_template
from datetime import datetime
from mysql.connector import Error
import logging
from utils.database import get_connection, _safe_close
from utils.helpers import serialize

appointment_bp = Blueprint('appointments', __name__)
logger = logging.getLogger(__name__)

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
    # ============================================
    # 1. CHECK AUTHENTICATION AND GET OWNER_ID
    # ============================================
    # Allow either regular logged-in users or mechanics/admins (mechanic session keys)
    if not (session.get("logged_in") or session.get("mechanic_logged_in")):
        return jsonify({"status": "error", "message": "Please login first"}), 401

    acting_mechanic = bool(session.get("mechanic_logged_in"))

    # Read request body early so mechanics may provide an explicit owner_id
    data = request.get_json() or {}
    car_plate = (data.get("car_plate") or "").strip()
    date = data.get("date")
    time = data.get("time")
    service_ids = data.get("service_ids", [])
    notes = data.get("notes", "")
    # Mechanics may pass an explicit owner_id in payload when acting on behalf of a user
    payload_owner_id = data.get("owner_id")
    owner_id = session.get("owner_id")
    if acting_mechanic and payload_owner_id:
        try:
            owner_id = int(payload_owner_id)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid owner_id in payload"}), 400
    # If not a mechanic and no owner linked, instruct to link an owner
    if not acting_mechanic and not owner_id:
        return jsonify({
            "status": "error",
            "message": "Your account is not linked to an owner profile. Please link an owner before booking.",
            "link_endpoint": "/owner/link"
        }), 400
    # If mechanic is acting but did not provide an owner_id, require it
    if acting_mechanic and not owner_id:
        return jsonify({"status": "error", "message": "Mechanic must provide an owner_id in the request body when booking on behalf of a user"}), 400
    
    # Optional car details
    car_model = (data.get("car_model") or "Unknown").strip()
    car_year = data.get("car_year") or datetime.now().year
    vin = (data.get("vin") or "").strip().upper() or None

    # ============================================
    # 3. VALIDATE INPUTS
    # ============================================
    if not car_plate or not date or not time or not service_ids:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    if not isinstance(service_ids, list):
        return jsonify({"status": "error", "message": "service_ids must be a list"}), 400

    try:
        requested_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        if requested_dt < datetime.now():
            return jsonify({"status": "error", "message": "Cannot book an appointment in the past"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid date/time format"}), 400

    # ============================================
    # 4. DATABASE OPERATIONS
    # ============================================
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        # Validate provided owner_id (if any) exists in owner table
        if owner_id:
            cursor.execute("SELECT 1 FROM owner WHERE Owner_ID = %s", (owner_id,))
            if not cursor.fetchone():
                conn.rollback()
                return jsonify({"status": "error", "message": "Provided owner_id does not exist"}), 400

        # ============================================
        # 4.1 CHECK TIME SLOT AVAILABILITY
        # ============================================
        cursor.execute("SELECT 1 FROM appointment WHERE Date = %s AND Time = %s", (date, time))
        if cursor.fetchone():
            conn.rollback()
            return jsonify({"status": "error", "message": "Time slot already booked"}), 409

        # ============================================
        # 4.2 CHECK VIN UNIQUENESS (if provided)
        # ============================================
        if vin:
            cursor.execute("SELECT Car_plate FROM car WHERE VIN = %s AND Car_plate != %s", (vin, car_plate))
            if cursor.fetchone():
                conn.rollback()
                return jsonify({"status": "error", "message": "VIN already in use by another car"}), 409

        # ============================================
        # 4.3 CHECK/CREATE CAR WITH OWNER_ID
        # ============================================
        cursor.execute("SELECT Car_plate, Owner_id FROM car WHERE Car_plate = %s", (car_plate,))
        car_result = cursor.fetchone()
        car_created = False
        
        if car_result:
            # Car exists - check ownership
            existing_owner_id = car_result[1]
            
            if existing_owner_id is None:
                # Car exists without owner - assign to current user
                cursor.execute(
                    "UPDATE car SET Owner_id = %s, Model = %s, Year = %s WHERE Car_plate = %s",
                    (owner_id, car_model, car_year, car_plate)
                )
                print(f"✅ Updated existing car {car_plate} with owner_id {owner_id}")
                
            elif existing_owner_id != owner_id:
                # Car belongs to a different owner. Do NOT change ownership here.
                # Allow booking by another authenticated user (e.g., admin/mechanic or
                # a user acting on behalf of the owner) while keeping Owner_id unchanged.
                # Update non-ownership fields (model/year/vin) but do not assign Owner_id.
                cursor.execute(
                    "UPDATE car SET Model = %s, Year = %s, VIN = %s WHERE Car_plate = %s",
                    (car_model, car_year, vin, car_plate)
                )
                print(f"ℹ️ Car {car_plate} belongs to owner {existing_owner_id}; booking by owner {owner_id} will not claim the car")
            else:
                # Car already belongs to this user - update details if needed
                cursor.execute(
                    "UPDATE car SET Model = %s, Year = %s, VIN = %s WHERE Car_plate = %s",
                    (car_model, car_year, vin, car_plate)
                )
                
        else:
            # Create new car linked to the logged-in owner
            cursor.execute(
                "INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (car_plate, car_model, car_year, vin, None, owner_id)
            )
            car_created = True
            print(f"✅ Created new car {car_plate} with owner_id {owner_id}")

        # ============================================
        # 4.4 CREATE APPOINTMENT RECORD
        # ============================================
        cursor.execute(
            "INSERT INTO appointment (Date, Time, Notes, Car_plate) VALUES (%s, %s, %s, %s)",
            (date, time, notes, car_plate),
        )
        appointment_id = cursor.lastrowid

        # ============================================
        # 4.5 ADD SERVICES
        # ============================================
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

        # ============================================
        # 4.6 COMMIT TRANSACTION
        # ============================================
        conn.commit()
        
        # Log successful booking
        print(f"✅ Appointment booked: ID={appointment_id}, Car={car_plate}, Owner={owner_id}, Date={date} {time}")
        
        return jsonify({
            "status": "success", 
            "message": f"Appointment booked for {car_plate} on {date} at {time}",
            "appointment_id": appointment_id,
            "owner_id": owner_id,
            "car_plate": car_plate,
            "car_created": car_created
        }), 201
        
    except Error as err:
        logger.error(f"Database error in book_appointment: {err}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in book_appointment: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500
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
         # In search_appointments_by_plate and get_appointment_by_id - REPLACE the queries with:
        cursor.execute("""
         SELECT a.Appointment_id, a.Date, a.Time, a.Notes, a.Car_plate,
         c.Model, c.Year, c.VIN, c.Owner_ID,
         o.Owner_Name, o.Owner_Email, o.PhoneNUMB,
         GROUP_CONCAT(s.Service_Type) AS Services,
         GROUP_CONCAT(s.Service_ID) AS service_ids
         FROM appointment a
         LEFT JOIN car c ON a.Car_plate = c.Car_plate
         LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID
         LEFT JOIN appointment_service aps ON a.Appointment_id = aps.Appointment_id
         LEFT JOIN service s ON aps.Service_ID = s.Service_ID
         WHERE a.Car_plate = %s
         GROUP BY a.Appointment_id
         ORDER BY a.Date, a.Time
         """, (car_plate,))
        
        appointments = cursor.fetchall()
        for appt in appointments:
            for k, v in appt.items():
                appt[k] = serialize(v)
        return jsonify({"status": "success", "appointments": appointments}), 200
    except Error as err:
        logger.error(f"Database error in search_appointments_by_plate: {err}")
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in search_appointments_by_plate: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
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
        logger.error(f"Database error in get_appointment_by_id: {err}")
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_appointment_by_id: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointments/select", methods=["POST"])
def select_appointment():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Please login first"}), 401

    data = request.get_json() or {}
    appointment_id = data.get("appointment_id")
    
    if not appointment_id:
        return jsonify({"status": "error", "message": "Missing appointment ID"}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # UPDATED QUERY - includes service_ids
        cursor.execute("""
            SELECT a.*, 
                   GROUP_CONCAT(s.Service_Type) as Services,
                   GROUP_CONCAT(s.Service_ID) as service_ids  # ← CRITICAL ADDITION
            FROM appointment a
            LEFT JOIN appointment_service aps ON a.Appointment_id = aps.Appointment_id
            LEFT JOIN service s ON aps.Service_ID = s.Service_ID
            WHERE a.Appointment_id = %s
            GROUP BY a.Appointment_id
        """, (appointment_id,))
        
        appointment = cursor.fetchone()
        
        if not appointment:
            return jsonify({"status": "error", "message": "Appointment not found"}), 404

        session['selected_appointment_id'] = appointment_id
        session['selected_appointment'] = {k: serialize(v) for k, v in appointment.items()}
        
        return jsonify({"status": "success", "message": "Appointment selected"}), 200

    except Error as err:
        logger.error(f"Database error in select_appointment: {err}")
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    finally:
        _safe_close(cursor, conn)

@appointment_bp.route("/appointments/current", methods=["GET"])
def get_current_appointment():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    appointment = session.get("selected_appointment")
    if not appointment:
        return jsonify({"status": "error", "message": "No appointment selected"}), 404
        
    return jsonify({"status": "success", "appointment": appointment})

@appointment_bp.route("/appointments/update", methods=["PUT"])
def update_selected_appointment():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    appointment_id = session.get("selected_appointment_id")
    if not appointment_id:
        return jsonify({"status": "error", "message": "No appointment selected"}), 400

    data = request.get_json() or {}
    date = data.get("date")
    time = data.get("time")
    
    try:
        date_time_str = f"{date} {time}"
        appointment_datetime = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
        if appointment_datetime < datetime.now():
            return jsonify({
                "status": "error",
                "message": "Cannot set appointment date/time in the past"
            }), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid date/time format"}), 400

    notes = data.get("notes", "")
    service_ids = data.get("service_ids", [])

    if not date or not time:
        return jsonify({"status": "error", "message": "Missing date or time"}), 400

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

        cursor.execute("SELECT 1 FROM appointment WHERE Appointment_id = %s", (appointment_id,))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"status": "error", "message": "Appointment not found"}), 404

        cursor.execute(
            "SELECT COUNT(*) FROM appointment WHERE Date = %s AND Time = %s AND Appointment_id != %s",
            (date, time, appointment_id),
        )
        if cursor.fetchone()[0] > 0:
            conn.rollback()
            return jsonify({"status": "error", "message": "Time slot already booked"}), 409

        cursor.execute(
            "UPDATE appointment SET Date = %s, Time = %s, Notes = %s WHERE Appointment_id = %s",
            (date, time, notes, appointment_id),
        )

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
        logger.error(f"Database error in update_selected_appointment: {err}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in update_selected_appointment: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500
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
        logger.error(f"Database error in delete_appointment: {err}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in delete_appointment: {e}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        _safe_close(cursor, conn)