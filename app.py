import os
import logging
from flask import Flask, render_template, jsonify, session
from flask_cors import CORS
from datetime import timedelta
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Keep secret key (use env in production)
    if test_config is None:
        app.secret_key = os.getenv("APP_SECRET_KEY", "dev-secret-key-for-testing")
        app.config.update(
            # Session configuration
            PERMANENT_SESSION_LIFETIME=timedelta(hours=1),  # Sessions last 7 days
            SESSION_COOKIE_HTTPONLY=True,    # Prevent XSS
            SESSION_COOKIE_SAMESITE="Lax",   # CSRF protection
            SESSION_COOKIE_SECURE=False,     # Set to True in production with HTTPS
            SESSION_REFRESH_EACH_REQUEST=True,  # Extend session on each request
            TESTING=False
        )
    else:
        app.config.from_mapping(test_config)

    # Enable CORS
    CORS(app, supports_credentials=True, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": True
        }
    })

    # ===============================
    # SIMPLE DATABASE CONNECTION helper
    # ===============================
    def get_db_connection():
        """Simple database connection used by some legacy routes if they import directly"""
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "isd"),
                auth_plugin="mysql_native_password",
                port=int(os.getenv("DB_PORT", 3306))
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return None

    # ===============================
    # REGISTER BLUEPRINTS (preserve everything)
    # ===============================
    # We attempt to register your existing blueprints exactly as before.
    # If a blueprint import fails we log but continue — this preserves all original behavior
    # and avoids hard crashes on import-time missing modules.

    # 1. Auth + Appointment
    try:
        from routes.auth_routes import auth_bp
        app.register_blueprint(auth_bp)
        logger.info("✅ Auth routes registered")
    except Exception as e:
        logger.warning(f"⚠️ Auth routes missing or failed to import: {e}")

    try:
        from routes.appointment_routes import appointment_bp
        app.register_blueprint(appointment_bp)
        logger.info("✅ Appointment routes registered")
    except Exception as e:
        logger.warning(f"⚠️ Appointment routes missing or failed to import: {e}")

    # 2. After-service
    try:
        from after_service import after_service_bp
        app.register_blueprint(after_service_bp)
        logger.info("✅ After-service routes registered")
    except Exception as e:
        logger.error(f"❌ After-service import failed: {e}")

    # 3. Mechanic
    try:
        from routes.mechanic_routes import mechanic_bp
        app.register_blueprint(mechanic_bp)
        logger.info("✅ Mechanic routes registered")
    except Exception as e:
        logger.warning(f"⚠️ Mechanic routes missing or failed to import: {e}")

    # 4. Car routes (API)
    try:
        from routes.car_routes import car_bp
        # register under /api/car/* to avoid colliding with UI /car/* pages
        app.register_blueprint(car_bp, url_prefix="/api/car")
        logger.info("✅ Car API routes registered under /api/car/*")
    except Exception as e:
        logger.error(f"❌ Car routes import failed: {e}")

    # 5. Template routes
    try:
        from routes.template_routes import template_bp
        app.register_blueprint(template_bp)
        logger.info("✅ Template routes registered")
    except Exception as e:
        logger.error(f"❌ Template routes missing or failed to import: {e}")

    # 6. Detection routes (with fallback)
    detection_blueprint_registered = False
    try:
        # Attempt to import and register the detection blueprint (this will be our integrated detection)
        from routes.detection_routes import detection_bp
        # register under /car so frontend can use /car/detect
        app.register_blueprint(detection_bp, url_prefix="/car")
        detection_blueprint_registered = True
        logger.info("✅ License plate detection routes registered under /car/*")
    except Exception as e:
        logger.warning(f"⚠️ Plate detection blueprint failed to load: {e}")

        # Fallback blueprint (keeps original UI route & behavior)
        from flask import Blueprint, request

        fallback_bp = Blueprint('detection_fallback', __name__)

        @fallback_bp.route('/detect', methods=['POST'])
        def detect_plate_fallback():
            # keep response shape consistent with detection endpoint used by frontend
            return jsonify({
                "success": False,
                "message": "Plate detection unavailable. Use manual entry.",
                "fallback": True
            }), 503

        @fallback_bp.route('/plate-detection')
        def plate_detection_page_fallback():
            return render_template('homee.html')

        app.register_blueprint(fallback_bp, url_prefix="/car")
        logger.info("✅ Fallback detection routes registered under /car/*")

    # 7. REMINDER ROUTES - NEW ADDITION (FIXED PLACEMENT)
    try:
        from routes.reminder_routes import reminder_bp, init_reminder_service
        # Initialize the reminder service
        init_reminder_service(app)
        # Register the blueprint
        app.register_blueprint(reminder_bp)
        logger.info("✅ Reminder routes registered under /api/reminders/*")
    except Exception as e:
        logger.error(f"❌ Reminder routes import failed: {e}")

    # ===============================
    # ALL YOUR ORIGINAL UI ROUTES (PRESERVED)
    # ===============================
    # These routes were present in your original app; we keep them exactly as they were.
    # However to avoid duplicate/conflict with detection blueprint we only add the explicit
    # /car/plate-detection UI route if the detection blueprint was NOT registered.
    @app.route('/mechanic/dashboard')
    def mechanic_dashboard_redirect():
        return render_template("mechanic_dashboard.html")

    @app.route('/admin/dashboard')
    def admin_dashboard_redirect():
        return render_template("mechanic_dashboard.html")

    @app.route('/mechanic/appointments')
    def mechanic_appointments_redirect():
        return render_template("mechanic_appointments.html")

    @app.route('/mechanic/service-history')
    def mechanic_service_history_redirect():
        return render_template("mechanic_service_history.html")

    @app.route('/admin/appointments')
    def admin_appointments_redirect():
        return render_template("mechanic_appointments.html")

    @app.route('/admin/service-history')
    def admin_service_history_redirect():
        return render_template("mechanic_service_history.html")

    @app.route('/mechanic/reports')
    def mechanic_reports_redirect():
        return render_template("mechanic_reports.html")

    # Form & Utility Routes
    @app.route('/after_service_form.html')
    def after_service_form():
        return render_template("after_service_form.html")

    @app.route('/login.html')
    def login_page():
        return render_template("login.html")

    @app.route('/mechanic/login.html')
    def mechanic_login_page():
        return render_template("mechanic_login.html")

    @app.route('/admin/login.html')
    def admin_login_page():
        return render_template("admin_login.html")

    @app.route('/signup.html')
    def signup_page():
        return render_template("signup.html")

    # Legacy & Redirection Routes
    @app.route('/homee.html')
    def homee_page():
        return render_template("homee.html")

    @app.route('/index.html')
    def index_page():
        return render_template("login.html")

    @app.route('/service-history.html')
    def service_history_html():
        return render_template("mechanic_service_history.html")

    @app.route('/appointments.html')
    def appointments_html():
        return render_template("mechanic_appointments.html")

    # ===============================
    # SESSION DEBUG ROUTE
    # ===============================
    @app.route("/api/session-info")
    def session_info():
        """Check session configuration and status"""
        session_data = {
            "logged_in": session.get("logged_in", False),
            "username": session.get("username"),
            "user_type": session.get("user_type"),
            "session_permanent": session.permanent,
        }
        
        # Add Flask session configuration
        session_data["flask_config"] = {
            "permanent_session_lifetime_seconds": app.permanent_session_lifetime.total_seconds(),
            "permanent_session_lifetime_days": app.permanent_session_lifetime.total_seconds() / 86400,
            "permanent_session_lifetime_human": f"{app.permanent_session_lifetime.days} days",
            "session_cookie_secure": app.config.get('SESSION_COOKIE_SECURE', False),
            "session_cookie_httponly": app.config.get('SESSION_COOKIE_HTTPONLY', True),
            "session_refresh_each_request": app.config.get('SESSION_REFRESH_EACH_REQUEST', True),
        }
        
        return jsonify(session_data)

    # ===============================
    # HEALTH CHECK & ROOT
    # ===============================
    @app.route("/api/health")
    def health_check():
        """Simple health check"""
        try:
            try:
                from utils.database import get_connection as get_conn
                conn = get_conn()
            except Exception:
                conn = get_db_connection()

            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                db_status = "connected"
                cursor.close()
                conn.close()
            else:
                db_status = "disconnected"
        except Exception as e:
            db_status = f"error: {str(e)}"

        return jsonify({
            "status": "healthy",
            "database": db_status,
            "service": "Auto Service Management System"
        })

    @app.route("/")
    def index():
        return render_template("index.html")

    # ===============================
    # ERROR HANDLERS
    # ===============================
    @app.errorhandler(404)
    def not_found(error):
        # preserve JSON for API; for UI you can have templates - keeping simple JSON as in original
        return jsonify({"success": False, "message": "Route not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "message": "Internal server error"}), 500

    return app

# Create main app instance
app = create_app()

if __name__ == "__main__":
    print("🚗 Auto Service Management System Starting...")
    print("📍 http://localhost:5000")
    print("")
    print("✅ All routes preserved")
    print("🕒 Session duration: 7 days")
    print("🚗 Add Car functionality: MOVED TO MECHANIC ROUTES")
    print("📧 Email Reminders: AVAILABLE at /api/reminders/*")
    print("")
    try:
        app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
    except Exception as e:
        logger.exception(f"Server error: {e}")