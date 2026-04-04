"""
Market Scanner — finds top N gainers/losers from F&O universe
and computes equal fund allocation.
"""
import logging
from typing import Optional
from services.fyers_client import FyersClient, FO_STOCKS, FO_MAP
from services.supertrend import analyse, result_to_dict

logger = logging.getLogger(__name__)


def scan_fo_universe(client: FyersClient, top_n: int = 5,
                     mode: str = "gainers",
                     run_supertrend: bool = True) -> list[dict]:
    """
    mode: gainers | losers | both
    Returns sorted list of dicts with quote + optional ST signal.
    """
    all_syms = [s["sym"] for s in FO_STOCKS]

    # Batch quotes (max 50 per Fyers API call)
    batch_size = 50
    all_quotes = {}
    for i in range(0, len(all_syms), batch_size):
        batch = all_syms[i:i + batch_size]
        try:
            q = client.get_quotes(batch)
            all_quotes.update(q)
        except Exception as e:
            logger.error(f"Quote batch error: {e}")

    enriched = []
    for s in FO_STOCKS:
        sym = s["sym"]
        q   = all_quotes.get(sym, {})
        if not q:
            continue

        # ── Fyers v3 field names ───────────────────────────────
        # ltp may be 0 when market is closed — use prev_close as fallback
        ltp        = float(q.get("ltp") or q.get("prev_close_price") or 0)
        prev_close = float(q.get("prev_close_price") or 0)
        if ltp == 0 and prev_close == 0:
            continue   # truly no data

        # % change: chp is the Fyers v3 field name
        pct = float(q.get("chp") or q.get("ch_1d") or q.get("change_percentage") or 0)
        ch  = float(q.get("ch")  or 0)

        # When market closed, compute pct from prev_close if chp missing
        if pct == 0 and prev_close > 0 and ltp > 0:
            pct = round((ltp - prev_close) / prev_close * 100, 2)

        enriched.append({
            "symbol":    sym,
            "name":      s["name"],
            "lot":       s["lot"],
            "ltp":       round(ltp, 2),
            "open":      round(float(q.get("open_price") or 0), 2),
            "high":      round(float(q.get("high_price") or 0), 2),
            "low":       round(float(q.get("low_price")  or 0), 2),
            "prev_close":round(prev_close, 2),
            "volume":    int(q.get("volume") or 0),
            "pct_change":round(pct, 2),
            "change":    round(ch, 2),
        })

    gainers = sorted(enriched, key=lambda x: x["pct_change"], reverse=True)
    losers  = sorted(enriched, key=lambda x: x["pct_change"])

    if mode == "gainers":
        top_list = gainers[:top_n]
    elif mode == "losers":
        top_list = losers[:top_n]
    else:  # both
        top_list = gainers[:top_n] + losers[:top_n]

    # Detect broker by client type for correct resolution
    from services.zerodha_client import ZerodhaClient as _ZC
    resolution = "day" if isinstance(client, _ZC) else "D"

    # Optionally run SuperTrend on each
    if run_supertrend:
        for item in top_list:
            try:
                hist = client.get_historical(item["symbol"], resolution=resolution)
                if hist and hist.get("s") == "ok":
                    result = analyse(item["symbol"], hist)
                    item["supertrend"] = result_to_dict(result)
                else:
                    logger.warning(f"ST hist error for {item['symbol']}: {hist}")
                    item["supertrend"] = None
            except Exception as e:
                logger.warning(f"ST failed for {item['symbol']}: {e}")
                item["supertrend"] = None
    return top_list


def compute_allocation(stocks: list[dict], total_funds: float,
                       allocation_mode: str = "equal") -> list[dict]:
    """
    allocation_mode: equal | proportional (by volume)
    Adds qty, allocated_amount, approx_value to each stock dict.
    """
    if not stocks:
        return []
    n = len(stocks)

    if allocation_mode == "equal":
        per_stock = total_funds / n
        weights   = [1.0] * n
    else:
        total_vol = sum(s.get("volume", 1) for s in stocks) or 1
        weights   = [s.get("volume", 1) / total_vol for s in stocks]
        per_stock = None  # unused

    result = []
    for i, s in enumerate(stocks):
        price = s.get("ltp", 1) or 1
        lot   = s.get("lot", 1) or 1
        if allocation_mode == "equal":
            alloc = per_stock
        else:
            alloc = total_funds * weights[i]

        # Qty in whole lots only
        shares_raw  = alloc / price
        lots_count  = max(1, int(shares_raw / lot))
        qty         = lots_count * lot
        actual_val  = qty * price

        result.append({
            **s,
            "allocated_amount": round(alloc, 2),
            "lots":             lots_count,
            "qty":              qty,
            "approx_value":     round(actual_val, 2),
        })
    return result
