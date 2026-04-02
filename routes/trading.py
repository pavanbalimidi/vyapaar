"""
Trading Routes — Dashboard, Scanner, Orders, Scheduler
"""
import logging
from datetime import datetime, date, time as dtime
from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash)
from flask_login import login_required, current_user
from db.models import db, FyersCredential, TradeHistory, ScheduledJob
from services.fyers_client import FyersClient, FO_STOCKS
from services.supertrend import analyse, result_to_dict
from services.scanner import scan_fo_universe, compute_allocation
from services.scheduler import schedule_job, unschedule_job

logger = logging.getLogger(__name__)
trading_bp = Blueprint("trading", __name__)


# ── HELPERS ───────────────────────────────────────────────────
def get_client() -> FyersClient | None:
    cred = FyersCredential.query.filter_by(user_id=current_user.id).first()
    if not cred or not cred.is_connected or not cred.access_token:
        return None
    return FyersClient(cred.app_id, cred.access_token)


def require_fyers(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        c = get_client()
        if not c:
            return jsonify({"ok": False, "error": "Fyers not connected or token expired. Please reconnect."}), 403
        return fn(*args, **kwargs, client=c)
    return wrapper


# ── DASHBOARD ─────────────────────────────────────────────────
@trading_bp.route("/")
@trading_bp.route("/dashboard")
@login_required
def dashboard():
    cred        = FyersCredential.query.filter_by(user_id=current_user.id).first()
    recent_trades = (TradeHistory.query
                     .filter_by(user_id=current_user.id)
                     .order_by(TradeHistory.created_at.desc())
                     .limit(10).all())
    pending_jobs = (ScheduledJob.query
                    .filter_by(user_id=current_user.id, status="pending")
                    .order_by(ScheduledJob.scheduled_time).all())
    return render_template("dashboard.html",
                           cred=cred,
                           recent_trades=recent_trades,
                           pending_jobs=pending_jobs)


# ─────────────────────────────────────────────────────────────
#  API ENDPOINTS (JSON)
# ─────────────────────────────────────────────────────────────

# ── MARKET DATA ───────────────────────────────────────────────
@trading_bp.route("/api/indices")
@login_required
@require_fyers
def api_indices(client):
    try:
        data = client.get_index_quotes()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@trading_bp.route("/api/quotes")
@login_required
@require_fyers
def api_quotes(client):
    syms = request.args.get("symbols", "").split(",")
    syms = [s.strip().upper() for s in syms if s.strip()]
    if not syms:
        return jsonify({"ok": False, "error": "No symbols provided"})
    try:
        data = client.get_quotes(syms)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ── SUPERTREND ANALYSIS ───────────────────────────────────────
@trading_bp.route("/api/analyse", methods=["POST"])
@login_required
@require_fyers
def api_analyse(client):
    data   = request.get_json(force=True)
    symbol = data.get("symbol", "").upper()
    period = int(data.get("period", 10))
    mult   = float(data.get("multiplier", 3.0))

    if not symbol:
        return jsonify({"ok": False, "error": "Symbol required"})
    try:
        hist = client.get_historical(symbol, resolution="D")
        if not hist or hist.get("s") != "ok":
            return jsonify({"ok": False, "error": f"Historical data error: {hist.get('message','')}"})
        result = analyse(symbol, hist, st_period=period, st_mult=mult)
        return jsonify({"ok": True, "data": result_to_dict(result)})
    except Exception as e:
        logger.error(f"Analyse error: {e}")
        return jsonify({"ok": False, "error": str(e)})


# ── SCANNER ───────────────────────────────────────────────────
@trading_bp.route("/api/scan", methods=["POST"])
@login_required
@require_fyers
def api_scan(client):
    data       = request.get_json(force=True)
    top_n      = int(data.get("top_n", 5))
    mode       = data.get("mode", "gainers")         # gainers | losers
    run_st     = bool(data.get("supertrend", True))
    try:
        results = scan_fo_universe(client, top_n=top_n,
                                   mode=mode, run_supertrend=run_st)
        return jsonify({"ok": True, "data": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Scan error: {e}")
        return jsonify({"ok": False, "error": str(e)})


# ── PLACE SINGLE ORDER ────────────────────────────────────────
@trading_bp.route("/api/order", methods=["POST"])
@login_required
@require_fyers
def api_place_order(client):
    data     = request.get_json(force=True)
    symbol   = data.get("symbol", "").upper()
    side     = data.get("side", "BUY").upper()
    qty      = int(data.get("qty", 1))
    otype    = data.get("order_type", "MARKET").upper()
    ptype    = data.get("product_type", "INTRADAY").upper()
    sl       = float(data.get("stop_loss", 0))
    tp       = float(data.get("take_profit", 0))
    st_data  = data.get("signal_data", {})

    if not symbol or qty <= 0:
        return jsonify({"ok": False, "error": "Invalid symbol or qty"})

    try:
        resp = client.place_order(symbol=symbol, side=side, qty=qty,
                                  order_type=otype, product_type=ptype,
                                  stop_loss=sl, take_profit=tp)
        order_id = resp.get("id", "")
        status   = "PLACED" if resp.get("s") == "ok" else "REJECTED"

        trade = TradeHistory(
            user_id=current_user.id,
            symbol=symbol, order_type=otype, side=side,
            quantity=qty, price=data.get("price", 0),
            order_id=order_id, status=status,
            strategy="manual", signal_data=st_data,
        )
        db.session.add(trade)
        db.session.commit()
        return jsonify({"ok": True, "order_id": order_id,
                        "status": status, "message": resp.get("message", "")})
    except Exception as e:
        logger.error(f"Order error: {e}")
        return jsonify({"ok": False, "error": str(e)})


# ── BULK ALLOCATION ORDER ─────────────────────────────────────
@trading_bp.route("/api/bulk-order", methods=["POST"])
@login_required
@require_fyers
def api_bulk_order(client):
    data     = request.get_json(force=True)
    stocks   = data.get("stocks", [])        # [{symbol, ltp, lot, supertrend, ...}]
    funds    = float(data.get("funds", 0))
    alloc_m  = data.get("allocation_mode", "equal")
    ptype    = data.get("product_type", "INTRADAY").upper()

    if not stocks or funds <= 0:
        return jsonify({"ok": False, "error": "Stocks and funds required"})

    allocated = compute_allocation(stocks, funds, alloc_m)
    results   = []
    for item in allocated:
        sym = item["symbol"]
        qty = item.get("qty", 0)
        if qty <= 0:
            continue
        st  = item.get("supertrend") or {}
        sl  = st.get("stop_loss", 0)
        tp  = st.get("take_profit", 0)
        try:
            resp     = client.place_order(symbol=sym, side="BUY", qty=qty,
                                          order_type="MARKET", product_type=ptype,
                                          stop_loss=sl, take_profit=tp)
            order_id = resp.get("id", "")
            status   = "PLACED" if resp.get("s") == "ok" else "REJECTED"
        except Exception as e:
            resp     = {}
            order_id = ""
            status   = f"ERROR: {e}"

        trade = TradeHistory(
            user_id=current_user.id,
            symbol=sym, order_type="MARKET", side="BUY",
            quantity=qty, price=item.get("ltp", 0),
            order_id=order_id, status=status,
            strategy="scanner_bulk", signal_data=st,
        )
        db.session.add(trade)
        results.append({"symbol": sym, "qty": qty,
                        "order_id": order_id, "status": status})

    db.session.commit()
    return jsonify({"ok": True, "orders": results, "count": len(results)})


# ── FUNDS & POSITIONS ────────────────────────────────────────
@trading_bp.route("/api/funds")
@login_required
@require_fyers
def api_funds(client):
    try:
        return jsonify({"ok": True, "data": client.get_funds()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@trading_bp.route("/api/positions")
@login_required
@require_fyers
def api_positions(client):
    try:
        return jsonify({"ok": True, "data": client.get_positions()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@trading_bp.route("/api/orders")
@login_required
@require_fyers
def api_orders(client):
    try:
        return jsonify({"ok": True, "data": client.get_orders()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ── DEBUG ENDPOINTS (check raw Fyers response) ───────────────
@trading_bp.route("/api/debug/quote")
@login_required
@require_fyers
def api_debug_quote(client):
    """Visit /api/debug/quote?sym=WIPRO to see raw Fyers response"""
    sym = request.args.get("sym", "WIPRO").upper()
    raw_quote = client.get_quotes([sym])
    raw_hist  = client.get_historical(sym, resolution="D")
    return jsonify({
        "quote_raw":   raw_quote,
        "hist_keys":   list(raw_hist.keys()) if raw_hist else [],
        "hist_candles_sample": raw_hist.get("candles", [])[:2] if raw_hist else [],
        "hist_t_sample":       raw_hist.get("t", [])[:2] if raw_hist else [],
    })

# ── TRADE HISTORY ─────────────────────────────────────────────
@trading_bp.route("/api/trades")
@login_required
def api_trades():
    limit  = int(request.args.get("limit", 50))
    trades = (TradeHistory.query
              .filter_by(user_id=current_user.id)
              .order_by(TradeHistory.created_at.desc())
              .limit(limit).all())
    return jsonify({"ok": True, "data": [{
        "id":        t.id,
        "symbol":    t.symbol,
        "side":      t.side,
        "qty":       t.quantity,
        "price":     float(t.price or 0),
        "order_id":  t.order_id,
        "status":    t.status,
        "strategy":  t.strategy,
        "created_at":t.created_at.isoformat(),
    } for t in trades]})


# ─────────────────────────────────────────────────────────────
#  SCHEDULER ROUTES
# ─────────────────────────────────────────────────────────────
@trading_bp.route("/scheduler")
@login_required
def scheduler_page():
    jobs = (ScheduledJob.query.filter_by(user_id=current_user.id)
            .order_by(ScheduledJob.created_at.desc()).all())
    return render_template("scheduler.html", jobs=jobs, fo_stocks=FO_STOCKS)


@trading_bp.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    jobs = ScheduledJob.query.filter_by(user_id=current_user.id).all()
    return jsonify({"ok": True, "data": [{
        "id":             j.id,
        "job_name":       j.job_name,
        "strategy":       j.strategy,
        "symbols":        j.symbols,
        "allocated_funds":float(j.allocated_funds or 0),
        "top_n":          j.top_n,
        "order_type":     j.order_type,
        "product_type":   j.product_type,
        "scheduled_time": j.scheduled_time.strftime("%H:%M") if j.scheduled_time else "",
        "scheduled_date": j.scheduled_date.isoformat() if j.scheduled_date else None,
        "is_recurring":   j.is_recurring,
        "status":         j.status,
        "last_run":       j.last_run.isoformat() if j.last_run else None,
    } for j in jobs]})


@trading_bp.route("/api/jobs", methods=["POST"])
@login_required
def api_create_job():
    from flask import current_app
    data = request.get_json(force=True)
    try:
        t_str = data.get("scheduled_time", "09:30")
        h, m  = map(int, t_str.split(":"))
        t_obj = dtime(h, m)
        d_str = data.get("scheduled_date")
        d_obj = date.fromisoformat(d_str) if d_str else None

        job = ScheduledJob(
            user_id        = current_user.id,
            job_name       = data.get("job_name", "My Job"),
            strategy       = data.get("strategy", "supertrend"),
            symbols        = data.get("symbols", []),
            allocated_funds= float(data.get("allocated_funds", 50000)),
            top_n          = int(data.get("top_n", 5)),
            order_type     = data.get("order_type", "MARKET").upper(),
            product_type   = data.get("product_type", "INTRADAY").upper(),
            scheduled_time = t_obj,
            scheduled_date = d_obj,
            is_recurring   = bool(data.get("is_recurring", False)),
            status         = "pending",
        )
        db.session.add(job)
        db.session.commit()
        schedule_job(job, current_app._get_current_object())
        return jsonify({"ok": True, "job_id": job.id,
                        "message": f"Job '{job.job_name}' scheduled for {t_str}"})
    except Exception as e:
        logger.error(f"Create job error: {e}")
        return jsonify({"ok": False, "error": str(e)})


@trading_bp.route("/api/jobs/<int:job_id>", methods=["DELETE"])
@login_required
def api_delete_job(job_id):
    job = ScheduledJob.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    unschedule_job(job_id)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"ok": True, "message": "Job deleted"})


@trading_bp.route("/api/jobs/<int:job_id>/pause", methods=["POST"])
@login_required
def api_pause_job(job_id):
    job = ScheduledJob.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    job.status = "paused" if job.status != "paused" else "pending"
    db.session.commit()
    if job.status == "paused":
        unschedule_job(job_id)
    else:
        from flask import current_app
        schedule_job(job, current_app._get_current_object())
    return jsonify({"ok": True, "status": job.status})
