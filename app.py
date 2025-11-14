from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_pyfile('config.py')
    
    # CORS configuration
    CORS(app, supports_credentials=True, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": True
        }
    })
    
    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.appointment_routes import appointment_bp
    from routes.template_routes import template_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(appointment_bp)
    app.register_blueprint(template_bp)
    
    return app

if __name__ == "__main__":
    app = create_app()
    print("Server starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)