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
        if not q or not q.get("ltp"):
            continue
        pct = q.get("ch_1d", q.get("chp", 0))   # % change field varies by endpoint
        enriched.append({
            "symbol":    sym,
            "name":      s["name"],
            "lot":       s["lot"],
            "ltp":       round(float(q.get("ltp", 0)), 2),
            "open":      round(float(q.get("open_price", 0)), 2),
            "high":      round(float(q.get("high_price", 0)), 2),
            "low":       round(float(q.get("low_price", 0)), 2),
            "prev_close":round(float(q.get("prev_close_price", 0)), 2),
            "volume":    int(q.get("volume", 0)),
            "pct_change":round(float(pct), 2),
            "change":    round(float(q.get("ch", 0)), 2),
        })

    gainers = sorted(enriched, key=lambda x: x["pct_change"], reverse=True)
    losers  = sorted(enriched, key=lambda x: x["pct_change"])

    if mode == "gainers":
        top_list = gainers[:top_n]
    elif mode == "losers":
        top_list = losers[:top_n]
    else:  # both
        top_list = gainers[:top_n] + losers[:top_n]

    # Optionally run SuperTrend on each
    if run_supertrend:
        for item in top_list:
            try:
                hist = client.get_historical(item["symbol"], resolution="D")
                if hist and hist.get("s") == "ok":
                    result = analyse(item["symbol"], hist)
                    item["supertrend"] = result_to_dict(result)
                else:
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
