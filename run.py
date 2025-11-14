from app import make_app

if __name__ == "__main__":
    app = make_app()
    print("Starting ISD Appointment System...")
    app.run(debug=True, host="0.0.0.0", port=5000)