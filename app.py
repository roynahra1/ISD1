import os
from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.getenv("APP_SECRET_KEY", os.urandom(24))
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False
    )

    CORS(app, supports_credentials=True, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": True
        }
    })

    # Import and register blueprints
    from routes.auth_routes import auth_bp
    from routes.appointment_routes import appointment_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(appointment_bp)
    
    return app

app = create_app()

if __name__ == "__main__":
    print("Server starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)