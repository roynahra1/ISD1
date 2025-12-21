from flask import Blueprint, jsonify, current_app, request
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import mysql.connector
import os
import logging
from datetime import datetime, date

reminder_bp = Blueprint('reminder', __name__, url_prefix='/api/reminders')

logger = logging.getLogger(__name__)

# Globals
mail = None
scheduler = None


# ===============================
# DATABASE CONNECTION
# ===============================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "isd"),
            auth_plugin="mysql_native_password",
            port=int(os.getenv("DB_PORT", 3306))
        )
        return conn
    except mysql.connector.Error as err:
        logger.error(f"❌ DB connection error: {err}")
        return None


# ===============================
# INITIALIZE MAIL + SCHEDULER
# ===============================
def init_reminder_service(app):
    global mail, scheduler

    # Validate required environment variables
    required_env = ["MAIL_USERNAME", "MAIL_PASSWORD"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        logger.error(f"❌ Missing required mail configuration: {', '.join(missing)}")
        logger.error("⚠️ Reminder service running without email sending enabled")
        app.config["MAIL_ENABLED"] = False
    else:
        app.config["MAIL_ENABLED"] = True

    # Mail settings
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

    # Initialize Flask-Mail if enabled
    try:
        if app.config["MAIL_ENABLED"]:
            from flask_mail import Mail
            mail = Mail(app)
            logger.info("📧 Flask-Mail initialized")
    except Exception as e:
        logger.error(f"❌ Flask-Mail init failed: {e}")
        app.config["MAIL_ENABLED"] = False

    # Start scheduler only once
    if not scheduler:
        logger.info("📆 Starting reminder scheduler (1st of month @ 9 AM)")
        scheduler = BackgroundScheduler()
        scheduler.add_job(send_reminders_thread, trigger='cron', day=1, hour=9, minute=0)
        scheduler.start()


# ===============================
# DB FETCH OWNERS + CARS
# ===============================
def get_all_owners_with_cars():
    conn = get_db_connection()
    if not conn:
        return []

    query = """
    SELECT 
        o.Owner_ID, o.Owner_Name, o.Owner_Email, o.PhoneNUMB,
        c.Car_plate, c.Model, c.Year, c.Next_Oil_Change
    FROM owner o
    LEFT JOIN car c ON o.Owner_ID = c.Owner_ID
    WHERE o.Owner_Email IS NOT NULL AND o.Owner_Email != ''
    ORDER BY o.Owner_ID;
    """

    owners = {}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        for row in cursor.fetchall():
            owner_id = row["Owner_ID"]
            if owner_id not in owners:
                owners[owner_id] = {
                    "name": row["Owner_Name"],
                    "email": row["Owner_Email"],
                    "phone": row["PhoneNUMB"],
                    "cars": []
                }
            
            if row["Car_plate"]:
                owners[owner_id]["cars"].append({
                    "plate": row["Car_plate"],
                    "model": row["Model"] or "-",
                    "year": row["Year"] or "-",
                    "next_oil_change": row["Next_Oil_Change"]
                })

        return list(owners.values())

    except Exception as e:
        logger.error(f"❌ Query error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ===============================
# SEND SINGLE EMAIL
# ===============================
def send_reminder_email(owner):
    if not current_app.config.get("MAIL_ENABLED"):
        logger.warning(f"⚠️ Email disabled — would have emailed {owner['email']}")
        return True

    from flask_mail import Message

    subject = "🚗 Your Monthly Service Reminder – ISF Garage"
    today = date.today().strftime("%B %d, %Y")

    body = f"""
Hello {owner['name']},

This is a monthly reminder from ISF Garage to keep your vehicle in great condition.

📅 Date: {today}

Your vehicles:
"""

    for i, car in enumerate(owner["cars"], 1):
        due = car["next_oil_change"]
        due_text = f" (Oil change due: {due})" if due else ""
        body += f"\n{i}. {car['model']} - Plate: {car['plate']}{due_text}"

    body += """

📌 Schedule Your Appointment Now:

Book Online: http://127.0.0.1:5000/index.html

Or contact us:
• Phone: +961-70631093
• Email: service@isfgarage.com

Thank you,
ISF Garage Team
"""

    try:
        msg = Message(subject, recipients=[owner["email"]], body=body)
        mail.send(msg)
        logger.info(f"📨 Sent reminder to {owner['email']}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send {owner['email']}: {e}")
        return False


# ===============================
# SEND URGENT EMAIL
# ===============================
def send_urgent_email_to_owner(plate_number, owner_name, owner_email, urgent_message):
    if not current_app.config.get("MAIL_ENABLED"):
        logger.warning(f"⚠️ Email disabled — would have sent urgent email to {owner_email}")
        return False

    from flask_mail import Message

    subject = f"⚠️ URGENT ATTENTION NEEDED - Vehicle {plate_number}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    body = f"""
URGENT NOTIFICATION - ISF GARAGE

Dear {owner_name},

This is an URGENT notification regarding your vehicle:

🚗 VEHICLE DETAILS:
• Plate Number: {plate_number}
• Time of Notification: {timestamp}
• Status: REQUIRES IMMEDIATE ATTENTION

📋 URGENT MESSAGE FROM MECHANIC:
{urgent_message}

⚠️ ACTION REQUIRED:
Please contact the garage IMMEDIATELY to address these critical issues.

📞 CONTACT INFORMATION:
• Phone: +961-70631093
• Email: service@isfgarage.com
• Address: ISD Garage, Main Street

Your prompt attention is required for vehicle safety.

Sincerely,
ISF Garage Service Team
"""

    try:
        msg = Message(
            subject=subject,
            recipients=[owner_email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        mail.send(msg)
        
        logger.info(f"📧 Sent URGENT email to {owner_email} for vehicle {plate_number}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send urgent email: {e}")
        return False


# ===============================
# BULK REMINDER THREAD
# ===============================
def send_monthly_reminders():
    owners = get_all_owners_with_cars()
    if not owners:
        return {"success": False, "message": "No owners found", "emails_sent": 0}

    sent = 0
    for owner in owners:
        if send_reminder_email(owner):
            sent += 1

    return {
        "success": True,
        "total": len(owners),
        "emails_sent": sent,
        "failed": len(owners) - sent
    }


def send_reminders_thread():
    logger.info("🧵 Sending monthly reminders in background thread...")
    threading.Thread(target=send_monthly_reminders, daemon=True).start()


# ===============================
# ROUTES
# ===============================
@reminder_bp.route('/send', methods=['POST'])
def trigger_reminders():
    result = send_monthly_reminders()
    return jsonify(result)


@reminder_bp.route('/urgent', methods=['POST'])
def send_urgent_email():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['plate_number', 'owner_email', 'urgent_message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    "success": False,
                    "message": f"Missing required field: {field}"
                }), 400
        
        plate_number = data['plate_number']
        owner_name = data.get('owner_name', 'Vehicle Owner')
        owner_email = data['owner_email']
        urgent_message = data['urgent_message']
        
        # Check if email is enabled
        if not current_app.config.get("MAIL_ENABLED"):
            return jsonify({
                "success": False,
                "message": "Email service is not enabled"
            }), 503
        
        # Send urgent email
        success = send_urgent_email_to_owner(plate_number, owner_name, owner_email, urgent_message)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Urgent email sent successfully",
                "plate_number": plate_number,
                "owner_email": owner_email
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to send urgent email"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error in urgent email endpoint: {e}")
        return jsonify({
            "success": False,
            "message": f"Internal server error: {str(e)}"
        }), 500


@reminder_bp.route('/test', methods=['GET'])
def test_reminders():
    owners = get_all_owners_with_cars()
    return jsonify({
        "status": "ready",
        "owners_found": len(owners),
        "mail_enabled": current_app.config.get("MAIL_ENABLED", False),
        "tip": "POST /api/reminders/send to send emails"
    })


@reminder_bp.route('/health')
def health_check():
    return jsonify({"status": "ok", "service": "email_reminders"})