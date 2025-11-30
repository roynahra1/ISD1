from flask import Blueprint, request, jsonify, render_template, session
import logging
import re
from datetime import datetime
from utils.database import get_connection, _safe_close

car_bp = Blueprint('car', __name__)

@car_bp.route('/test')
def test_route():
    return jsonify({
        'status': 'success', 
        'message': 'Car routes are working!',
        'timestamp': datetime.now().isoformat()
    })

@car_bp.route("/add", methods=["POST"])
def add_car():
    """Add new car to system using plate from session"""
    data = request.get_json() or {}
    logging.info(f"Add car data received: {data}")

    # Try to get plate from session first, then from form data
    car_plate = session.get('detected_plate') or data.get("car_plate", "").strip().upper()
    model = data.get("model", "").strip()
    year = data.get("year")
    vin = data.get("vin", "").strip().upper()
    next_oil_change = data.get("next_oil_change")
    owner_type = data.get("owner_type")
    owner_phone = data.get("PhoneNUMB", "").strip()
    owner_name = data.get("owner_name", "").strip()
    owner_email = data.get("owner_email", "").strip()
    
    # New service fields
    current_mileage = data.get("current_mileage", 0)
    last_service_date = data.get("last_service_date")
    service_notes = data.get("service_notes", "Initial car registration")

    # Input Validation
    if not all([car_plate, model, year, vin, owner_type]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    if not re.match(r"^[A-Z0-9]{4,8}$", car_plate):
        return jsonify({"status": "error", "message": "Invalid license plate format (4-8 alphanumeric characters)"}), 400

    try:
        year = int(year)
        current_year = datetime.now().year
        if year < 1900 or year > current_year:
            return jsonify({"status": "error", "message": f"Year must be between 1900 and {current_year}"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Year must be a valid number"}), 400

    if len(vin) != 17:
        return jsonify({"status": "error", "message": "VIN must be exactly 17 characters"}), 400

    if next_oil_change:
        try:
            next_oil_change = datetime.strptime(next_oil_change, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid date format for next oil change (YYYY-MM-DD)"}), 400

    if last_service_date:
        try:
            last_service_date = datetime.strptime(last_service_date, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid date format for last service date (YYYY-MM-DD)"}), 400

    try:
        current_mileage = int(current_mileage)
        if current_mileage < 0:
            return jsonify({"status": "error", "message": "Mileage cannot be negative"}), 400
    except (ValueError, TypeError):
        current_mileage = 0

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if car already exists
        cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (car_plate,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "Car with this plate already exists"}), 409

        # Check if VIN already exists
        cursor.execute("SELECT Car_plate FROM car WHERE VIN = %s", (vin,))
        existing_vin = cursor.fetchone()
        if existing_vin:
            return jsonify({"status": "error", "message": f"VIN number already exists for car plate: {existing_vin[0]}"}), 409

        # Owner Handling
        owner_id = None
        
        if owner_type == "existing":
            if not owner_phone:
                return jsonify({"status": "error", "message": "Phone number required for existing owner"}), 400
                
            cursor.execute("SELECT Owner_ID FROM owner WHERE PhoneNUMB = %s", (owner_phone,))
            result = cursor.fetchone()
            if not result:
                return jsonify({"status": "error", "message": "Owner with this phone number not found"}), 404
            owner_id = result[0]

        elif owner_type == "new":
            if not all([owner_name, owner_phone]):
                return jsonify({"status": "error", "message": "New owner name and phone number required"}), 400
                
            # Check if owner already exists with this phone
            cursor.execute("SELECT Owner_ID FROM owner WHERE PhoneNUMB = %s", (owner_phone,))
            result = cursor.fetchone()
            
            if result:
                owner_id = result[0]
            else:
                # Create new owner
                cursor.execute(
                    "INSERT INTO owner (Owner_Name, Owner_Email, PhoneNUMB) VALUES (%s, %s, %s)",
                    (owner_name, owner_email or None, owner_phone)
                )
                owner_id = cursor.lastrowid
        else:
            return jsonify({"status": "error", "message": "Invalid owner type"}), 400

        # Insert Car
        cursor.execute("""
            INSERT INTO car (Car_plate, Model, Year, VIN, Next_Oil_Change, Owner_ID)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (car_plate, model, year, vin, next_oil_change or None, owner_id))

        # Create initial service history with the new fields
        # ✅ CORRECT - no History_ID
        cursor.execute("""
        INSERT INTO service_history 
         (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
          VALUES (%s, %s, %s, %s, %s)
           """, (datetime.now().date(), current_mileage, datetime.now().date(), service_notes, car_plate))

        conn.commit()
        
        # Clear the plate from session after successful car addition
        if 'detected_plate' in session:
            session.pop('detected_plate')
            session.modified = True
        
        logging.info(f"Car added successfully: {car_plate} for owner {owner_id}")
        return jsonify({
            "status": "success", 
            "message": "Car added successfully", 
            "car_plate": car_plate,
            "owner_id": owner_id
        }), 201

    except Exception as err:
        logging.error(f"Add car failed: {err}")
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(err)}"}), 500
    finally:
        _safe_close(cursor, conn)

@car_bp.route('/check/<car_plate>', methods=['GET'])
def check_car_exists(car_plate):
    """Check if car exists in database"""
    logging.info(f"🔍 Checking car plate: {car_plate}")
    
    if not car_plate or not re.match(r"^[A-Z0-9]{4,8}$", car_plate.upper()):
        logging.warning(f"Invalid plate format: {car_plate}")
        return jsonify({
            'exists': False,
            'message': 'Invalid plate format'
        })
        
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        logging.info(f"Executing database query for plate: {car_plate.upper()}")
        
        # Query to get comprehensive car info
        cursor.execute("""
            SELECT 
                c.Car_plate,
                c.Model,
                c.Year,
                c.VIN,
                c.Next_Oil_Change,
                o.Owner_ID,
                o.Owner_Name,
                o.Owner_Email,
                o.PhoneNUMB
            FROM car c 
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID 
            WHERE c.Car_plate = %s
        """, (car_plate.upper(),))
        
        car = cursor.fetchone()
        logging.info(f"Database result: {car}")
        
        if car:
            # Get latest service history
            cursor.execute("""
                SELECT Service_Date, Mileage, Last_Oil_Change, Notes 
                FROM service_history 
                WHERE Car_plate = %s 
                ORDER BY History_ID DESC 
                LIMIT 1
            """, (car_plate.upper(),))
            
            service_info = cursor.fetchone()
            if service_info:
                car.update(service_info)
            
            logging.info(f"✅ Car found: {car_plate}")
            return jsonify({
                'exists': True,
                'car': car,
                'message': 'Car found in database'
            })
        else:
            logging.info(f"❌ Car not found: {car_plate}")
            return jsonify({
                'exists': False,
                'message': f'Car with plate {car_plate} not found in database'
            })
            
    except Exception as e:
        logging.error(f"🚨 Check car exists error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500
    finally:
        _safe_close(cursor, conn)

@car_bp.route('/detect', methods=['POST'])
def detect_plate():
    """Simulate license plate detection"""
    try:
        # For demo purposes - simulate plate detection
        import random
        
        # Sample plates from your database for realistic testing
        detected_plates = ['R123456', 'ABC123', 'XYZ789', 'S222', 'A1111', 'W123456']
        distances = ['2-4 meters', '4-7 meters', '7-10 meters', '10-15 meters']
        
        # Use plates that exist in your database
        plate_number = random.choice(detected_plates)
        confidence = round(random.uniform(0.85, 0.98), 2)
        distance = random.choice(distances)
        
        logging.info(f"Plate detection simulated: {plate_number}")
        
        return jsonify({
            'success': True,
            'plate_number': plate_number,
            'confidence': confidence,
            'distance': distance,
            'message': 'Plate detected successfully'
        })
        
    except Exception as e:
        logging.error(f"Plate detection error: {e}")
        return jsonify({
            'success': False,
            'message': f'Detection error: {str(e)}'
        }), 500

@car_bp.route('/cars', methods=['GET'])
def get_all_cars():
    """Get all cars"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
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
            ORDER BY c.Car_plate
        ''')
        
        cars = cursor.fetchall()
        return jsonify({"success": True, "cars": cars, "count": len(cars)})
        
    except Exception as e:
        logging.error(f"Get cars error: {e}")
        return jsonify({"success": False, "message": "Failed to fetch cars"}), 500
    finally:
        _safe_close(cursor, conn)

# Session-based plate storage routes
@car_bp.route('/store-plate', methods=['POST'])
def store_plate():
    """Store detected plate in session"""
    try:
        data = request.get_json()
        plate = data.get('plate', '').strip().upper()
        
        if plate and re.match(r"^[A-Z0-9]{4,8}$", plate):
            session['detected_plate'] = plate
            session.modified = True
            logging.info(f"Plate stored in session: {plate}")
            return jsonify({
                'status': 'success', 
                'message': 'Plate stored successfully',
                'plate': plate
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Invalid plate format'
            }), 400
            
    except Exception as e:
        logging.error(f"Store plate error: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Storage error: {str(e)}'
        }), 500

@car_bp.route('/clear-plate', methods=['POST'])
def clear_plate():
    """Clear plate from session"""
    try:
        plate = session.pop('detected_plate', None)
        session.modified = True
        return jsonify({
            'status': 'success', 
            'message': 'Plate cleared from session',
            'cleared_plate': plate
        })
    except Exception as e:
        logging.error(f"Clear plate error: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Clear error: {str(e)}'
        }), 500

@car_bp.route('/stored-plate', methods=['GET'])
def get_stored_plate():
    """Get the plate stored in session"""
    try:
        plate = session.get('detected_plate', '')
        return jsonify({
            'status': 'success',
            'plate': plate,
            'has_plate': bool(plate)
        })
    except Exception as e:
        logging.error(f"Get stored plate error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to get stored plate: {str(e)}'
        }), 500

# Template routes
@car_bp.route('/service-menu')
def service_menu():
    """Serve the service menu page"""
    # Only use session, no URL parameters
    plate = session.get('detected_plate', '')
    return render_template('service_menu.html', plate=plate)

@car_bp.route('/appointment')
def appointment_page():
    """Serve the appointment booking page"""
    # Only use session, no URL parameters
    plate = session.get('detected_plate', '')
    return render_template('appointment.html', plate=plate)

@car_bp.route('/service-history')
def service_history_page():
    """Serve the service history page"""
    # Only use session, no URL parameters
    plate = session.get('detected_plate', '')
    return render_template('service_history.html', plate=plate)

@car_bp.route('/license-detection')
def license_detection_page():
    """Serve the license detection page"""
    return render_template('license_dection.html')

@car_bp.route('/addCar')
def add_car_form():
    """Serve the add car form with pre-filled plate from session ONLY"""
    # CRITICAL: Only use session, ignore any URL parameters
    plate = session.get('detected_plate', '')
    logging.info(f"Add car form requested. Session plate: {plate}")
    
    # Render template with session plate only (no owners list)
    return render_template('addCar.html', pre_filled_plate=plate)

@car_bp.route('/dashboard')
def car_dashboard():
    """Car management dashboard"""
    return render_template('car_dashboard.html')

@car_bp.route('/after_service_form.html')
def after_service_form():
    """Serve the after service form page"""
    plate = session.get('detected_plate', '')
    logging.info(f"After service form requested. Session plate: {plate}")
    return render_template('after_service_form.html', plate=plate)

@car_bp.route('/check-session-plate', methods=['GET'])
def check_session_plate():
    """Check if there's a plate in session and return its status"""
    try:
        plate = session.get('detected_plate', '')
        has_plate = bool(plate)
        
        return jsonify({
            'status': 'success',
            'has_plate': has_plate,
            'plate': plate,
            'message': 'Session plate check completed'
        })
    except Exception as e:
        logging.error(f"Check session plate error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to check session plate: {str(e)}'
        }), 500

# After Service Form API Routes - IMPROVED VERSION
@car_bp.route('/api/car/<car_plate>', methods=['GET'])
def get_car_info_api(car_plate):
    """Get car information by plate number for after-service form"""
    try:
        # Validate plate format
        if not car_plate or not re.match(r"^[A-Z0-9]{4,8}$", car_plate.upper()):
            return jsonify({
                'status': 'error',
                'message': 'Invalid license plate format'
            }), 400

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get car information with owner details
        cursor.execute("""
            SELECT 
                c.Car_plate,
                c.Model,
                c.Year,
                c.VIN,
                c.Next_Oil_Change,
                o.Owner_ID,
                o.Owner_Name,
                o.Owner_Email,
                o.PhoneNUMB
            FROM car c 
            LEFT JOIN owner o ON c.Owner_ID = o.Owner_ID 
            WHERE c.Car_plate = %s
        """, (car_plate.upper(),))
        
        car = cursor.fetchone()
        
        if car:
            # Get latest service history
            cursor.execute("""
                SELECT 
                    Service_Date, 
                    Mileage, 
                    Last_Oil_Change, 
                    Notes 
                FROM service_history 
                WHERE Car_plate = %s 
                ORDER BY History_ID DESC 
                LIMIT 1
            """, (car_plate.upper(),))
            
            service_info = cursor.fetchone()
            if service_info:
                car.update(service_info)
            
            logging.info(f"✅ Car info fetched for: {car_plate}")
            return jsonify({
                'status': 'success',
                'data': car
            })
        else:
            logging.info(f"❌ Car not found: {car_plate}")
            return jsonify({
                'status': 'error',
                'message': 'Car not found in database'
            }), 404
            
    except Exception as e:
        logging.error(f"Get car info API error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Database error'
        }), 500
    finally:
        _safe_close(cursor, conn)

@car_bp.route('/api/update-car-service', methods=['POST'])
def update_car_service():
    """Update car information and create service history with automatic oil change calculation"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        # Extract and validate data from request
        car_plate = data.get('car_plate', '').strip().upper()
        model = data.get('model', '').strip()
        year = data.get('year')
        vin = data.get('vin', '').strip().upper()
        service_date = data.get('service_date')
        mileage = data.get('mileage')
        next_oil_change = data.get('next_oil_change')
        notes = data.get('notes', '').strip()
        services_performed = data.get('services_performed', [])
        
        # Validation
        if not car_plate:
            return jsonify({'status': 'error', 'message': 'License plate is required'}), 400
        
        if not re.match(r"^[A-Z0-9]{4,8}$", car_plate):
            return jsonify({'status': 'error', 'message': 'Invalid license plate format'}), 400
        
        if year:
            try:
                year = int(year)
                current_year = datetime.now().year
                if year < 1900 or year > current_year:
                    return jsonify({'status': 'error', 'message': f'Year must be between 1900 and {current_year}'}), 400
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'message': 'Invalid year format'}), 400
        
        if vin and len(vin) != 17:
            return jsonify({'status': 'error', 'message': 'VIN must be exactly 17 characters'}), 400
        
        if mileage:
            try:
                mileage = int(mileage)
                if mileage < 0:
                    return jsonify({'status': 'error', 'message': 'Mileage cannot be negative'}), 400
            except (ValueError, TypeError):
                return jsonify({'status': 'error', 'message': 'Invalid mileage format'}), 400
        
        # Date validation
        today = datetime.now().date()
        
        # Service date validation
        if service_date:
            try:
                service_date = datetime.strptime(service_date, "%Y-%m-%d").date()
                if service_date > today:
                    return jsonify({'status': 'error', 'message': 'Service date cannot be in the future'}), 400
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid service date format (YYYY-MM-DD)'}), 400
        else:
            service_date = today
        
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Start transaction
            conn.start_transaction()
            
            # Check if car exists
            cursor.execute("SELECT Car_plate FROM car WHERE Car_plate = %s", (car_plate,))
            if not cursor.fetchone():
                return jsonify({'status': 'error', 'message': 'Car not found in database'}), 404
            
            # 🔥 AUTOMATICALLY GET LAST OIL CHANGE FROM DATABASE
            cursor.execute("""
                SELECT Last_Oil_Change 
                FROM service_history 
                WHERE Car_plate = %s 
                ORDER BY History_ID DESC 
                LIMIT 1
            """, (car_plate,))
            
            result = cursor.fetchone()
            if result and result[0]:
                last_oil_change = result[0]
                logging.info(f"🔍 Auto-fetched last oil change from DB: {last_oil_change}")
            else:
                # No history found, use service date
                last_oil_change = service_date
                logging.info(f"📝 No oil change history found, using service date: {last_oil_change}")
            
            # Additional time validations
            if last_oil_change > service_date:
                return jsonify({'status': 'error', 'message': 'Last oil change date cannot be after service date'}), 400
            
            # 🔥 AUTOMATIC NEXT OIL CHANGE CALCULATION (+6 months)
            auto_calculated = False
            if not next_oil_change:
                # Calculate 6 months from last oil change date
                next_oil_change_date = last_oil_change
                months_to_add = 6
                
                # Handle month overflow
                new_month = next_oil_change_date.month + months_to_add
                new_year = next_oil_change_date.year
                
                while new_month > 12:
                    new_month -= 12
                    new_year += 1
                
                # Handle day adjustment for months with fewer days
                try:
                    next_oil_change_date = next_oil_change_date.replace(year=new_year, month=new_month)
                except ValueError:
                    # If day is invalid for target month (e.g., Feb 30), go to last day of month
                    if new_month == 2:
                        # Check for leap year
                        if (new_year % 4 == 0 and new_year % 100 != 0) or (new_year % 400 == 0):
                            last_day = 29
                        else:
                            last_day = 28
                        next_oil_change_date = next_oil_change_date.replace(year=new_year, month=new_month, day=last_day)
                    else:
                        # For other months, use the original day or last day of month
                        import calendar
                        last_day = calendar.monthrange(new_year, new_month)[1]
                        next_oil_change_date = next_oil_change_date.replace(year=new_year, month=new_month, day=min(next_oil_change_date.day, last_day))
                
                next_oil_change = next_oil_change_date.strftime("%Y-%m-%d")
                auto_calculated = True
                logging.info(f"📅 Auto-calculated next oil change: {next_oil_change}")
            else:
                # Validate provided next oil change date
                try:
                    next_oil_change_date = datetime.strptime(next_oil_change, "%Y-%m-%d").date()
                    if next_oil_change_date <= today:
                        return jsonify({'status': 'error', 'message': 'Next oil change date must be in the future'}), 400
                except ValueError:
                    return jsonify({'status': 'error', 'message': 'Invalid next oil change date format (YYYY-MM-DD)'}), 400
                auto_calculated = False
            
            # Check VIN uniqueness if provided
            if vin:
                cursor.execute("SELECT Car_plate FROM car WHERE VIN = %s AND Car_plate != %s", (vin, car_plate))
                existing_vin = cursor.fetchone()
                if existing_vin:
                    return jsonify({'status': 'error', 'message': f'VIN already exists for car: {existing_vin[0]}'}), 409
            
            # Validate service IDs
            valid_service_ids = {1, 2, 3, 4, 5}  # Based on your service table
            if services_performed:
                invalid_services = [s for s in services_performed if int(s) not in valid_service_ids]
                if invalid_services:
                    return jsonify({'status': 'error', 'message': f'Invalid service IDs: {invalid_services}'}), 400
            
            # Update car information
            update_fields = []
            update_values = []
            
            if model:
                update_fields.append("Model = %s")
                update_values.append(model)
            if year:
                update_fields.append("Year = %s")
                update_values.append(year)
            if vin:
                update_fields.append("VIN = %s")
                update_values.append(vin)
            
            # Always update next oil change (auto-calculated or provided)
            update_fields.append("Next_Oil_Change = %s")
            update_values.append(next_oil_change)
            
            if update_fields:
                update_values.append(car_plate)
                cursor.execute(f"""
                    UPDATE car 
                    SET {', '.join(update_fields)}
                    WHERE Car_plate = %s
                """, update_values)
            
            # 🔥 FIX: Let MySQL handle the auto-increment by NOT specifying History_ID
            # Create service history record WITHOUT History_ID (let DB auto-increment)
            cursor.execute("""
                INSERT INTO service_history 
                (Service_Date, Mileage, Last_Oil_Change, Notes, Car_plate)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                service_date,
                mileage,
                last_oil_change,
                notes or "After-service update",
                car_plate
            ))
            
            # Get the auto-generated History_ID
            history_id = cursor.lastrowid
            
            # Link services performed (if any)
            if services_performed:
                for service_id in services_performed:
                    cursor.execute("""
                        INSERT INTO service_history_service 
                        (History_ID, Service_ID)
                        VALUES (%s, %s)
                    """, (history_id, int(service_id)))
            
            conn.commit()
            
            logging.info(f"✅ Car service updated for: {car_plate}, History ID: {history_id}")
            logging.info(f"📅 Last oil change: {last_oil_change}")
            logging.info(f"📅 Next oil change: {next_oil_change} (auto-calculated: {auto_calculated})")
            
            return jsonify({
                'status': 'success',
                'message': 'Car information updated and service logged successfully',
                'history_id': history_id,
                'car_plate': car_plate,
                'last_oil_change': last_oil_change.strftime("%Y-%m-%d"),
                'next_oil_change': next_oil_change,
                'auto_calculated': auto_calculated
            })
            
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Update car service error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Database error: {str(e)}'
            }), 500
        finally:
            _safe_close(cursor, conn)
            
    except Exception as e:
        logging.error(f"Update car service error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500