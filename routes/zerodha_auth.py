"""
Zerodha Kite Connect Auth Routes
──────────────────────────────────
GET  /zerodha/setup      → Show setup form + HOW TO guide
POST /zerodha/setup      → Save API key + secret
GET  /zerodha/auth       → Redirect to Kite login
GET  /zerodha/callback   → Handle request_token → access_token
GET  /zerodha/disconnect → Clear tokens
GET  /zerodha/status     → JSON status
POST /zerodha/switch     → Switch active broker to zerodha
"""
import logging
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, current_app, jsonify)
from flask_login import login_required, current_user
from db.models import db, ZerodhaCredential, User
from services.zerodha_client import (ZerodhaClient,
                                     generate_zerodha_auth_url,
                                     exchange_zerodha_token)

logger      = logging.getLogger(__name__)
zerodha_bp  = Blueprint("zerodha", __name__, url_prefix="/zerodha")


# ── SETUP ─────────────────────────────────────────────────────
@zerodha_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    cred = ZerodhaCredential.query.filter_by(user_id=current_user.id).first()

    if request.method == "POST":
        api_key    = request.form.get("api_key", "").strip()
        api_secret = request.form.get("api_secret", "").strip()

        if not api_key or not api_secret:
            flash("API Key and API Secret are required.", "error")
            return render_template("zerodha_setup.html", cred=cred)

        if not cred:
            cred = ZerodhaCredential(user_id=current_user.id)
            db.session.add(cred)

        cred.api_key    = api_key
        cred.api_secret = api_secret
        cred.is_connected = False
        cred.access_token = None
        db.session.commit()
        flash("Zerodha credentials saved. Click Connect to login.", "success")
        return redirect(url_for("zerodha.setup"))

    redirect_uri = current_app.config.get(
        "ZERODHA_REDIRECT_URI",
        url_for("zerodha.callback", _external=True)
    )
    return render_template("zerodha_setup.html", cred=cred,
                           redirect_uri=redirect_uri)


# ── STEP 1: Redirect to Kite login ────────────────────────────
@zerodha_bp.route("/auth")
@login_required
def auth_redirect():
    cred = ZerodhaCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        flash("Set up your Zerodha credentials first.", "error")
        return redirect(url_for("zerodha.setup"))
    auth_url = generate_zerodha_auth_url(cred.api_key)
    return redirect(auth_url)


# ── STEP 2: Callback — Kite redirects here with request_token ─
@zerodha_bp.route("/callback")
@login_required
def callback():
    request_token = request.args.get("request_token")
    status        = request.args.get("status", "")

    if status != "success" or not request_token:
        error = request.args.get("message", "Login failed or cancelled")
        flash(f"Zerodha login failed: {error}", "error")
        return redirect(url_for("zerodha.setup"))

    cred = ZerodhaCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        flash("No Zerodha credentials found.", "error")
        return redirect(url_for("zerodha.setup"))

    try:
        result = exchange_zerodha_token(cred.api_key, cred.api_secret, request_token)
        if result.get("s") != "ok":
            flash(f"Token exchange failed: {result.get('message')}", "error")
            return redirect(url_for("zerodha.setup"))

        cred.access_token    = result["access_token"]
        cred.request_token   = request_token
        cred.token_expiry    = datetime.utcnow().replace(
            hour=23, minute=59, second=59)   # expires at midnight IST
        cred.zerodha_user_id = result.get("user_id", "")
        cred.is_connected    = True

        # Auto-switch active broker to zerodha
        current_user.active_broker = "zerodha"
        db.session.commit()

        flash(f"✅ Zerodha connected as {cred.zerodha_user_id}!", "success")
        return redirect(url_for("trading.dashboard"))

    except Exception as e:
        logger.error(f"Zerodha callback error: {e}")
        flash(f"Error: {e}", "error")
        return redirect(url_for("zerodha.setup"))


# ── DISCONNECT ────────────────────────────────────────────────
@zerodha_bp.route("/disconnect")
@login_required
def disconnect():
    cred = ZerodhaCredential.query.filter_by(user_id=current_user.id).first()
    if cred:
        cred.access_token = None
        cred.is_connected = False
        db.session.commit()
    if current_user.active_broker == "zerodha":
        current_user.active_broker = "fyers"
        db.session.commit()
    flash("Zerodha disconnected.", "info")
    return redirect(url_for("zerodha.setup"))


# ── SWITCH ACTIVE BROKER ──────────────────────────────────────
@zerodha_bp.route("/switch", methods=["POST"])
@login_required
def switch_broker():
    broker = request.form.get("broker", "fyers")
    if broker not in ("fyers", "zerodha"):
        return jsonify({"ok": False, "error": "Invalid broker"})
    current_user.active_broker = broker
    db.session.commit()
    flash(f"Switched to {broker.title()}.", "success")
    return redirect(url_for("trading.dashboard"))


# ── STATUS ────────────────────────────────────────────────────
@zerodha_bp.route("/status")
@login_required
def status():
    cred = ZerodhaCredential.query.filter_by(user_id=current_user.id).first()
    if not cred:
        return jsonify({"connected": False, "message": "No credentials"})
    return jsonify({
        "connected":   cred.is_connected,
        "token_valid": cred.is_token_valid(),
        "user_id":     cred.zerodha_user_id,
        "expires":     cred.token_expiry.isoformat() if cred.token_expiry else None,
    })
