"""
APScheduler-based job runner for scheduled trades.
Jobs are stored in the PostgreSQL DB and run at the scheduled time.
"""
import logging
import pytz
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

logger  = logging.getLogger(__name__)
IST     = pytz.timezone("Asia/Kolkata")
_sched  = None   # singleton


def get_scheduler() -> BackgroundScheduler:
    global _sched
    if _sched is None:
        _sched = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            timezone=IST,
        )
        _sched.start()
        logger.info("APScheduler started")
    return _sched


def schedule_job(job: "ScheduledJob", app) -> None:  # noqa: F821
    """Register a DB ScheduledJob with APScheduler."""
    sched = get_scheduler()
    job_id = f"job_{job.id}"

    if sched.get_job(job_id):
        sched.remove_job(job_id)

    t = job.scheduled_time
    trigger = CronTrigger(
        hour=t.hour, minute=t.minute, second=0,
        timezone=IST,
    )
    sched.add_job(
        func=_run_job,
        trigger=trigger,
        id=job_id,
        kwargs={"job_id": job.id, "app": app},
        replace_existing=True,
        misfire_grace_time=300,  # 5-min grace
    )
    logger.info(f"Scheduled job {job_id} at {t}")


def unschedule_job(job_id: int) -> None:
    sched = get_scheduler()
    jid   = f"job_{job_id}"
    if sched.get_job(jid):
        sched.remove_job(jid)
        logger.info(f"Removed scheduled job {jid}")


def _run_job(job_id: int, app) -> None:
    """Execute a ScheduledJob — runs inside scheduler thread."""
    with app.app_context():
        from db.models import db, ScheduledJob, TradeHistory, FyersCredential
        from services.fyers_client import FyersClient
        from services.scanner import scan_fo_universe, compute_allocation
        from services.supertrend import analyse, result_to_dict

        job  = db.session.get(ScheduledJob, job_id)
        if not job or job.status == "paused":
            return

        logger.info(f"Running job {job_id}: {job.job_name}")
        job.status   = "running"
        job.last_run = datetime.utcnow()
        db.session.commit()

        try:
            cred = FyersCredential.query.filter_by(user_id=job.user_id).first()
            if not cred or not cred.is_connected or not cred.access_token:
                raise RuntimeError("Fyers not connected / token expired")

            client = FyersClient(cred.app_id, cred.access_token)

            # ── Pick stocks ──────────────────────────────────
            if job.strategy == "supertrend":
                # Scan top N gainers with ST confirmation
                top = scan_fo_universe(client, top_n=job.top_n,
                                       mode="gainers", run_supertrend=True)
                # Filter only BUY signals
                buy_stocks = [s for s in top
                              if s.get("supertrend", {}) and
                              s["supertrend"].get("signal") == "BUY"]
                stocks = buy_stocks[:job.top_n] or top[:job.top_n]
            else:
                # Use explicitly stored symbols
                syms    = job.symbols or []
                quotes  = client.get_quotes(syms)
                stocks  = [{"symbol": s, "ltp": quotes.get(s, {}).get("ltp", 0),
                             "lot": 1} for s in syms]

            if not stocks:
                raise RuntimeError("No stocks matched strategy criteria")

            # ── Compute allocation ───────────────────────────
            allocated = compute_allocation(stocks, float(job.allocated_funds))

            # ── Place orders ─────────────────────────────────
            for item in allocated:
                sym = item["symbol"]
                qty = item["qty"]
                if qty <= 0:
                    continue
                st  = item.get("supertrend") or {}
                sl  = st.get("stop_loss", 0)
                tp  = st.get("take_profit", 0)

                resp = client.place_order(
                    symbol=sym, side="BUY", qty=qty,
                    order_type=job.order_type,
                    product_type=job.product_type,
                    stop_loss=sl, take_profit=tp,
                )
                order_id = resp.get("id", "")
                status   = "PLACED" if resp.get("s") == "ok" else "REJECTED"

                trade = TradeHistory(
                    user_id=job.user_id,
                    symbol=sym,
                    order_type=job.order_type,
                    side="BUY",
                    quantity=qty,
                    price=item["ltp"],
                    order_id=order_id,
                    status=status,
                    strategy=job.strategy,
                    signal_data=st,
                    scheduled_job_id=job.id,
                )
                db.session.add(trade)

            job.status = "done"
            if not job.is_recurring:
                job.status = "done"
            db.session.commit()
            logger.info(f"Job {job_id} completed: {len(allocated)} orders placed")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job.status = "failed"
            job.notes  = str(e)
            db.session.commit()
