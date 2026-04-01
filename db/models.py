from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ──────────────────────────────────────────────────────────────
#  USER  (app-level registration)
# ──────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "vyapaar_users"

    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(255), unique=True, nullable=False)
    username     = db.Column(db.String(100), unique=True, nullable=False)
    password_hash= db.Column(db.String(255), nullable=False)
    full_name    = db.Column(db.String(255))
    phone        = db.Column(db.String(20))
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    fyers_cred   = db.relationship("FyersCredential", back_populates="user",
                                   uselist=False, cascade="all, delete-orphan")
    scheduled_jobs = db.relationship("ScheduledJob", back_populates="user",
                                     cascade="all, delete-orphan")
    trades       = db.relationship("TradeHistory", back_populates="user",
                                   cascade="all, delete-orphan")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def __repr__(self):
        return f"<User {self.username}>"


# ──────────────────────────────────────────────────────────────
#  FYERS CREDENTIALS  (one per user)
# ──────────────────────────────────────────────────────────────
class FyersCredential(db.Model):
    __tablename__ = "fyers_credentials"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("vyapaar_users.id", ondelete="CASCADE"),
                               unique=True, nullable=False)
    app_id         = db.Column(db.String(100), nullable=False)        # Client ID from myapi.fyers.in
    secret_key     = db.Column(db.String(255), nullable=False)        # Secret key
    redirect_url   = db.Column(db.String(500))
    access_token   = db.Column(db.Text)                               # Daily token (expires at midnight)
    refresh_token  = db.Column(db.Text)
    token_expiry   = db.Column(db.DateTime)
    fyers_user_id  = db.Column(db.String(100))                        # e.g. XJ12345
    is_connected   = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="fyers_cred")

    def is_token_valid(self):
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.utcnow() < self.token_expiry

    def __repr__(self):
        return f"<FyersCred user={self.user_id} app={self.app_id}>"


# ──────────────────────────────────────────────────────────────
#  SCHEDULED JOB
# ──────────────────────────────────────────────────────────────
class ScheduledJob(db.Model):
    __tablename__ = "vyapaar_scheduled_jobs"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("vyapaar_users.id", ondelete="CASCADE"),
                                nullable=False)
    job_name        = db.Column(db.String(255), nullable=False)
    strategy        = db.Column(db.String(100), default="supertrend")  # supertrend | manual | scanner
    symbols         = db.Column(db.JSON)                                # ["RELIANCE", "TCS", ...]
    allocated_funds = db.Column(db.Numeric(15, 2))
    top_n           = db.Column(db.Integer, default=5)
    order_type      = db.Column(db.String(20), default="MARKET")       # MARKET | LIMIT
    product_type    = db.Column(db.String(20), default="INTRADAY")     # INTRADAY | CNC | MARGIN
    scheduled_time  = db.Column(db.Time, nullable=False)               # HH:MM to execute
    scheduled_date  = db.Column(db.Date)                               # None = every day
    is_recurring    = db.Column(db.Boolean, default=False)
    status          = db.Column(db.String(50), default="pending")      # pending | running | done | failed | paused
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_run        = db.Column(db.DateTime)
    next_run        = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="scheduled_jobs")

    def __repr__(self):
        return f"<ScheduledJob {self.job_name} user={self.user_id}>"


# ──────────────────────────────────────────────────────────────
#  TRADE HISTORY
# ──────────────────────────────────────────────────────────────
class TradeHistory(db.Model):
    __tablename__ = "vyapaar_trade_history"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("vyapaar_users.id", ondelete="CASCADE"),
                            nullable=False)
    symbol      = db.Column(db.String(100), nullable=False)
    exchange    = db.Column(db.String(20), default="NSE")
    order_type  = db.Column(db.String(50))    # MARKET | LIMIT | SL | SL-M
    side        = db.Column(db.String(10))    # BUY | SELL
    quantity    = db.Column(db.Integer)
    price       = db.Column(db.Numeric(15, 2))
    order_id    = db.Column(db.String(255))   # Fyers order ID
    status      = db.Column(db.String(50))    # PLACED | FILLED | REJECTED | CANCELLED
    strategy    = db.Column(db.String(100))   # supertrend | scanner | manual
    signal_data = db.Column(db.JSON)          # {supertrend_val, atr, signal, ...}
    pnl         = db.Column(db.Numeric(15, 2))
    scheduled_job_id = db.Column(db.Integer, db.ForeignKey("vyapaar_scheduled_jobs.id",
                                                            ondelete="SET NULL"), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    filled_at   = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="trades")

    def __repr__(self):
        return f"<Trade {self.side} {self.symbol} x{self.quantity}>"
