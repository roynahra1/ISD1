import os
from flask import Flask
from flask_cors import CORS

def create_app(test_config=None):
    app = Flask(__name__)
    
    # Configuration
    if test_config is None:
        app.secret_key = os.getenv("APP_SECRET_KEY", "dev-secret-key-for-testing")
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax", 
            SESSION_COOKIE_SECURE=False,
            TESTING=False
        )
    else:
        app.config.from_mapping(test_config)
    
    # Enable CORS for all routes
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
    try:
        from routes.auth_routes import auth_bp
        from routes.appointment_routes import appointment_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(appointment_bp)
    except ImportError as e:
        print(f"Warning: Could not import blueprints: {e}")
    
    return app

# Create app instance for production
app = create_app()

if __name__ == "__main__":
    print("Server starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)