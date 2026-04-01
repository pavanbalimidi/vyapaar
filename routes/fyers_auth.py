"""
Fyers OAuth Routes
──────────────────
GET  /fyers/setup          → Show form to enter App ID + Secret
POST /fyers/setup          → Save credentials, generate auth URL
GET  /fyers/auth           → Redirect user to Fyers login
GET  /fyers/callback       → Handle auth_code → access_token
POST /fyers/token          → Manual token entry (paste from browser)
GET  /fyers/disconnect     → Clear tokens
"""
import hashlib
import logging
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, current_app, session, jsonify)
from flask_login import login_required, current_user
from db.models import db, FyersCredential
from services.fyers_client import generate_auth_url, exchange_auth_code, FyersClient

logger = logging.getLogger(__name__)
fyers_bp = Blueprint("fyers", __name__, url_prefix="/fyers")


# ── SETUP ─────────────────────────────────────────────────────
@fyers_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        app_id     = request.form.get("app_id", "").strip()
        secret_key = request.form.get("secret_key", "").strip()
        redirect_u = request.form.get("redirect_url",
                     current_app.config["FYERS_REDIRECT_URI"]).strip()

        if not app_id or not secret_key:
            flash("App ID and Secret Key are required.", "error")
            return render_template("fyers_setup.html", cred=cred)

        if not cred:
            cred = FyersCredential(user_id=current_user.id)
            db.session.add(cred)

        cred.app_id      = app_id
        cred.secret_key  = secret_key
        cred.redirect_url= redirect_u
        cred.is_connected= False
        cred.access_token= None
        db.session.commit()
        flash("Credentials saved. Now connect your Fyers account.", "success")
        return redirect(url_for("fyers.auth_redirect"))

    return render_template("fyers_setup.html", cred=cred,
                           redirect_uri=current_app.config["FYERS_REDIRECT_URI"])


# ── STEP 1: Redirect to Fyers login ───────────────────────────
@fyers_bp.route("/auth")
@login_required
def auth_redirect():
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        flash("Set up your Fyers credentials first.", "error")
        return redirect(url_for("fyers.setup"))
    try:
        auth_url = generate_auth_url(cred.app_id, cred.redirect_url)
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Auth URL error: {e}")
        flash(f"Could not generate Fyers auth URL: {e}", "error")
        return redirect(url_for("fyers.setup"))


# ── STEP 2a: Auto callback (redirect_uri = /fyers/callback) ───
@fyers_bp.route("/callback")
@login_required
def callback():
    auth_code = request.args.get("auth_code") or request.args.get("code")
    if not auth_code:
        flash("No auth_code received from Fyers.", "error")
        return redirect(url_for("fyers.setup"))
    return _exchange_and_save(auth_code)


# ── STEP 2b: Manual token paste ───────────────────────────────
@fyers_bp.route("/token", methods=["GET", "POST"])
@login_required
def manual_token():
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        auth_code = request.form.get("auth_code", "").strip()
        if auth_code:
            return _exchange_and_save(auth_code)
        # Or direct access_token paste
        access_token = request.form.get("access_token", "").strip()
        if access_token and cred:
            cred.access_token  = access_token
            cred.token_expiry  = datetime.utcnow() + timedelta(hours=24)
            cred.is_connected  = True
            # verify
            try:
                client  = FyersClient(cred.app_id, access_token)
                profile = client.get_profile()
                if profile.get("s") == "ok":
                    cred.fyers_user_id = profile.get("data", {}).get("fy_id", "")
                    flash(f"Connected as {cred.fyers_user_id}!", "success")
                else:
                    flash(f"Token may be invalid: {profile.get('message')}", "warning")
            except Exception as e:
                flash(f"Token saved but verification failed: {e}", "warning")
            db.session.commit()
            return redirect(url_for("trading.dashboard"))
        flash("Please provide auth_code or access_token.", "error")

    return render_template("fyers_token.html", cred=cred)


def _exchange_and_save(auth_code: str):
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        flash("No credentials on file.", "error")
        return redirect(url_for("fyers.setup"))
    try:
        result = exchange_auth_code(
            cred.app_id,
            cred.secret_key,
            auth_code,
            redirect_uri=cred.redirect_url,   # ← must match what generated the auth URL
        )
        if result.get("s") != "ok":
            flash(f"Token exchange failed: {result.get('message','Unknown error')}", "error")
            return redirect(url_for("fyers.manual_token"))

        cred.access_token  = result.get("access_token")
        cred.refresh_token = result.get("refresh_token")
        cred.token_expiry  = datetime.utcnow() + timedelta(hours=24)
        cred.is_connected  = True

        # Fetch profile to confirm
        client = FyersClient(cred.app_id, cred.access_token)
        profile = client.get_profile()
        if profile.get("s") == "ok":
            cred.fyers_user_id = profile.get("data", {}).get("fy_id", "")
        db.session.commit()
        flash(f"✅ Fyers connected as {cred.fyers_user_id}!", "success")
        return redirect(url_for("trading.dashboard"))

    except Exception as e:
        logger.error(f"Token exchange exception: {e}")
        flash(f"Error: {e}", "error")
        return redirect(url_for("fyers.manual_token"))


# ── DISCONNECT ────────────────────────────────────────────────
@fyers_bp.route("/disconnect")
@login_required
def disconnect():
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if cred:
        cred.access_token  = None
        cred.refresh_token = None
        cred.is_connected  = False
        db.session.commit()
    flash("Fyers account disconnected.", "info")
    return redirect(url_for("fyers.setup"))


# ── STATUS API ────────────────────────────────────────────────
@fyers_bp.route("/status")
@login_required
def status():
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        return jsonify({"connected": False, "message": "No credentials"})
    return jsonify({
        "connected":    cred.is_connected,
        "token_valid":  cred.is_token_valid(),
        "fyers_user":   cred.fyers_user_id,
        "expires":      cred.token_expiry.isoformat() if cred.token_expiry else None,
    })
