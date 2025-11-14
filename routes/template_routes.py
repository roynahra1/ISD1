from flask import Blueprint, render_template, redirect, session

template_bp = Blueprint('templates', __name__)

@template_bp.route("/")
def index():
    return redirect("/appointment.html")

@template_bp.route("/login.html")
def login_page():
    return render_template("login.html")

@template_bp.route("/signup.html")
def signup_page():
    return render_template("signup.html")

@template_bp.route("/appointment.html")
def serve_form():
    return render_template("appointment.html")

@template_bp.route("/viewAppointment/search")
def serve_view():
    return render_template("viewAppointment.html")

@template_bp.route("/updateAppointment.html")
def serve_update():
    if not session.get("logged_in"):
        return redirect("/login.html")
    if not session.get("selected_appointment"):
        return redirect("/viewAppointment/search")
    return render_template("updateAppointment.html")