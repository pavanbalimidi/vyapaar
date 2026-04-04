"""
VYAPAAR — Main Flask Application
Run: python app.py
"""
import logging
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import Config
from db.models import db, User
from routes.auth import auth_bp
from routes.fyers_auth import fyers_bp
from routes.zerodha_auth import zerodha_bp
from routes.trading import trading_bp

# ── LOGGING ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── DB ────────────────────────────────────────────────────
    db.init_app(app)

    # ── LOGIN MANAGER ─────────────────────────────────────────
    lm = LoginManager()
    lm.init_app(app)
    lm.login_view      = "auth.login"
    lm.login_message   = "Please log in to access the terminal."
    lm.login_message_category = "info"

    @lm.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    # ── BLUEPRINTS ────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(fyers_bp)
    app.register_blueprint(zerodha_bp)
    app.register_blueprint(trading_bp)

    # ── ROOT ──────────────────────────────────────────────────
    @app.route("/")
    def root():
        return redirect(url_for("trading.dashboard"))

    # ── DB CREATE ─────────────────────────────────────────────
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables verified/created.")
        except Exception as e:
            logger.error(f"DB init error (run migrations.sql manually): {e}")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
