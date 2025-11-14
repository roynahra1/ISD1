from app import create_app

if __name__ == "__main__":
    app = create_app()
    print("🚀 Development server starting on http://localhost:5000")
    print("📁 Debug mode: ON")
    app.run(debug=True, host='0.0.0.0', port=5000)