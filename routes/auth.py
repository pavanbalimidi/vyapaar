from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from db.models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("trading.dashboard"))

    if request.method == "POST":
        email     = request.form.get("email", "").strip().lower()
        username  = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        phone     = request.form.get("phone", "").strip()
        password  = request.form.get("password", "")
        confirm   = request.form.get("confirm_password", "")

        errors = []
        if not email:      errors.append("Email is required.")
        if not username:   errors.append("Username is required.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm: errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("Email already registered.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form_data=request.form)

        user = User(email=email, username=username,
                    full_name=full_name, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form_data={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("trading.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        user = (User.query.filter_by(email=identifier).first() or
                User.query.filter_by(username=identifier).first())

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            nxt = request.args.get("next") or url_for("trading.dashboard")
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(nxt)
        flash("Invalid credentials.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))
