"""
Zerodha Kite Connect v3 Client Wrapper
Handles auth URL, token exchange, quotes, historical, orders.

Install: pip install kiteconnect
Docs: https://kite.trade/docs/connect/v3/
"""
import logging
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus

logger = logging.getLogger(__name__)

PERM_MSG = (
    "Kite Connect app missing permissions. "
    "Go to developers.kite.trade → Edit your app → enable: "
    "Market quotes and data, Historical data, Orders, Holdings, Profile. "
    "Then reconnect your token."
)



# ── Zerodha F&O stocks with lot sizes ────────────────────────
# Same universe as Fyers but Kite uses different symbol format
ZD_FO_STOCKS = [
    {"sym": "RELIANCE",    "lot": 250,  "name": "Reliance Industries",      "exch": "NSE"},
    {"sym": "TCS",         "lot": 150,  "name": "Tata Consultancy Services", "exch": "NSE"},
    {"sym": "INFY",        "lot": 300,  "name": "Infosys Ltd",               "exch": "NSE"},
    {"sym": "HDFCBANK",    "lot": 550,  "name": "HDFC Bank",                 "exch": "NSE"},
    {"sym": "ICICIBANK",   "lot": 700,  "name": "ICICI Bank",                "exch": "NSE"},
    {"sym": "SBIN",        "lot": 1500, "name": "State Bank of India",       "exch": "NSE"},
    {"sym": "BAJFINANCE",  "lot": 125,  "name": "Bajaj Finance",             "exch": "NSE"},
    {"sym": "KOTAKBANK",   "lot": 400,  "name": "Kotak Mahindra Bank",       "exch": "NSE"},
    {"sym": "LT",          "lot": 175,  "name": "Larsen & Toubro",           "exch": "NSE"},
    {"sym": "AXISBANK",    "lot": 625,  "name": "Axis Bank",                 "exch": "NSE"},
    {"sym": "WIPRO",       "lot": 1500, "name": "Wipro Ltd",                 "exch": "NSE"},
    {"sym": "MARUTI",      "lot": 100,  "name": "Maruti Suzuki",             "exch": "NSE"},
    {"sym": "TATAMOTORS",  "lot": 550,  "name": "Tata Motors",               "exch": "NSE"},
    {"sym": "TECHM",       "lot": 600,  "name": "Tech Mahindra",             "exch": "NSE"},
    {"sym": "SUNPHARMA",   "lot": 350,  "name": "Sun Pharmaceutical",        "exch": "NSE"},
    {"sym": "DRREDDY",     "lot": 125,  "name": "Dr. Reddys Lab",            "exch": "NSE"},
    {"sym": "BHARTIARTL",  "lot": 950,  "name": "Bharti Airtel",             "exch": "NSE"},
    {"sym": "NTPC",        "lot": 3000, "name": "NTPC Ltd",                  "exch": "NSE"},
    {"sym": "ONGC",        "lot": 1925, "name": "Oil & Natural Gas",         "exch": "NSE"},
    {"sym": "ADANIPORTS",  "lot": 1250, "name": "Adani Ports",               "exch": "NSE"},
    {"sym": "TATASTEEL",   "lot": 5500, "name": "Tata Steel",                "exch": "NSE"},
    {"sym": "HINDALCO",    "lot": 2150, "name": "Hindalco Industries",       "exch": "NSE"},
    {"sym": "JSWSTEEL",    "lot": 1350, "name": "JSW Steel",                 "exch": "NSE"},
    {"sym": "BAJAJ-AUTO",  "lot": 250,  "name": "Bajaj Auto",                "exch": "NSE"},
    {"sym": "INDUSINDBK",  "lot": 500,  "name": "IndusInd Bank",             "exch": "NSE"},
    {"sym": "HCLTECH",     "lot": 700,  "name": "HCL Technologies",          "exch": "NSE"},
    {"sym": "DIVISLAB",    "lot": 200,  "name": "Divis Laboratories",        "exch": "NSE"},
    {"sym": "ASIANPAINT",  "lot": 300,  "name": "Asian Paints",              "exch": "NSE"},
    {"sym": "TITAN",       "lot": 375,  "name": "Titan Company",             "exch": "NSE"},
    {"sym": "GRASIM",      "lot": 475,  "name": "Grasim Industries",         "exch": "NSE"},
    {"sym": "POWERGRID",   "lot": 2700, "name": "Power Grid Corp",           "exch": "NSE"},
    {"sym": "COALINDIA",   "lot": 4200, "name": "Coal India",                "exch": "NSE"},
    {"sym": "ULTRACEMCO",  "lot": 100,  "name": "UltraTech Cement",          "exch": "NSE"},
    {"sym": "CHOLAFIN",    "lot": 1250, "name": "Cholamandalam Inv",         "exch": "NSE"},
    {"sym": "SBILIFE",     "lot": 750,  "name": "SBI Life Insurance",        "exch": "NSE"},
    {"sym": "HDFCLIFE",    "lot": 1100, "name": "HDFC Life Insurance",       "exch": "NSE"},
    {"sym": "NAUKRI",      "lot": 125,  "name": "Info Edge",                 "exch": "NSE"},
    {"sym": "MPHASIS",     "lot": 400,  "name": "Mphasis Ltd",               "exch": "NSE"},
    {"sym": "PERSISTENT",  "lot": 250,  "name": "Persistent Systems",        "exch": "NSE"},
    {"sym": "LTIM",        "lot": 150,  "name": "LTIMindtree",               "exch": "NSE"},
    {"sym": "BANKBARODA",  "lot": 5850, "name": "Bank of Baroda",            "exch": "NSE"},
    {"sym": "CANBK",       "lot": 1875, "name": "Canara Bank",               "exch": "NSE"},
    {"sym": "PNB",         "lot": 8000, "name": "Punjab National Bank",      "exch": "NSE"},
    {"sym": "CIPLA",       "lot": 650,  "name": "Cipla Ltd",                 "exch": "NSE"},
    {"sym": "HEROMOTOCO",  "lot": 300,  "name": "Hero MotoCorp",             "exch": "NSE"},
    {"sym": "EICHERMOT",   "lot": 175,  "name": "Eicher Motors",             "exch": "NSE"},
    {"sym": "M&M",         "lot": 700,  "name": "Mahindra & Mahindra",       "exch": "NSE"},
    {"sym": "VEDL",        "lot": 4100, "name": "Vedanta Ltd",               "exch": "NSE"},
    {"sym": "AMBUJACEM",   "lot": 1500, "name": "Ambuja Cements",            "exch": "NSE"},
    {"sym": "ICICIPRULI",  "lot": 1500, "name": "ICICI Prudential Life",     "exch": "NSE"},
]

ZD_FO_MAP    = {s["sym"]: s for s in ZD_FO_STOCKS}
# ── HARDCODED NSE EQUITY INSTRUMENT TOKENS ──────────────────────
# Avoids downloading the full 3MB instruments CSV on every historical call.
# Tokens are stable for NSE equity (EQ) — refresh annually if symbols change.
ZD_INSTRUMENT_TOKENS = {
    "RELIANCE": 738561, "TCS": 2953217, "INFY": 408065,
    "HDFCBANK": 341249, "ICICIBANK": 1270529, "SBIN": 779521,
    "BAJFINANCE": 81153, "KOTAKBANK": 492033, "LT": 2939649,
    "AXISBANK": 1510401, "WIPRO": 969473, "MARUTI": 2815745,
    "TATAMOTORS": 884737, "TECHM": 3465729, "SUNPHARMA": 857857,
    "DRREDDY": 225537, "BHARTIARTL": 2714625, "NTPC": 2977281,
    "ONGC": 633601, "ADANIPORTS": 3861249, "TATASTEEL": 895745,
    "HINDALCO": 348929, "JSWSTEEL": 3001089, "BAJAJ-AUTO": 4267265,
    "INDUSINDBK": 1346049, "HCLTECH": 1850625, "DIVISLAB": 2800641,
    "ASIANPAINT": 60417, "TITAN": 897537, "GRASIM": 315393,
    "POWERGRID": 3834113, "COALINDIA": 5215745, "ULTRACEMCO": 2952193,
    "CHOLAFIN": 175361, "SBILIFE": 5582849, "HDFCLIFE": 119553,
    "NAUKRI": 3430401, "MPHASIS": 548353, "PERSISTENT": 3074561,
    "LTIM": 4752385, "BANKBARODA": 1195009, "CANBK": 2763265,
    "PNB": 2730497, "CIPLA": 177665, "HEROMOTOCO": 345089,
    "EICHERMOT": 232961, "M&M": 519937, "VEDL": 784129,
    "AMBUJACEM": 1459457, "ICICIPRULI": 4299265,
}

# Zerodha index instrument tokens
ZD_INDEX_TOKENS = {
    "NIFTY 50":     256265,
    "BANK NIFTY":   260105,
    "FIN NIFTY":    257801,
    "MIDCAP NIFTY": 288009,
    "SENSEX":       265,
}


ZD_INDICES = {
    "NIFTY 50":     "NSE:NIFTY 50",
    "BANK NIFTY":   "NSE:NIFTY BANK",
    "FIN NIFTY":    "NSE:NIFTY FIN SERVICE",
    "MIDCAP NIFTY": "NSE:NIFTY MIDCAP 50",
    "SENSEX":       "BSE:SENSEX",
}


# ── AUTH HELPERS ─────────────────────────────────────────────
def generate_zerodha_auth_url(api_key: str) -> str:
    """
    Kite Connect OAuth login URL.
    After login, Zerodha redirects to your redirect_url with ?request_token=xxx
    """
    base   = "https://kite.zerodha.com/connect/login"
    params = urlencode({"api_key": api_key, "v": "3"}, quote_via=quote_plus)
    return f"{base}?{params}"


def exchange_zerodha_token(api_key: str, api_secret: str,
                           request_token: str) -> dict:
    """
    Exchange request_token for access_token.
    Checksum = sha256(api_key + request_token + api_secret)
    """
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=api_key)
        data = kite.generate_session(request_token, api_secret=api_secret)
        return {"s": "ok", "access_token": data["access_token"],
                "user_id": data.get("user_id", ""),
                "user_name": data.get("user_name", "")}
    except Exception as e:
        # Fallback: direct API call without SDK
        import requests as req
        checksum = hashlib.sha256(
            f"{api_key}{request_token}{api_secret}".encode()
        ).hexdigest()
        resp = req.post(
            "https://api.kite.trade/session/token",
            data={
                "api_key":       api_key,
                "request_token": request_token,
                "checksum":      checksum,
            },
            headers={"X-Kite-Version": "3"},
            timeout=15,
        )
        d = resp.json()
        if d.get("status") == "success":
            return {"s": "ok",
                    "access_token": d["data"]["access_token"],
                    "user_id":      d["data"].get("user_id", ""),
                    "user_name":    d["data"].get("user_name", "")}
        return {"s": "error", "message": d.get("message", str(e))}


# ── ZERODHA CLIENT ───────────────────────────────────────────
class ZerodhaClient:
    """Wraps kiteconnect for a single user's session."""

    BASE = "https://api.kite.trade"

    def __init__(self, api_key: str, access_token: str):
        self.api_key      = api_key
        self.access_token = access_token
        self._headers     = {
            "X-Kite-Version":  "3",
            "Authorization":   f"token {api_key}:{access_token}",
            "Content-Type":    "application/x-www-form-urlencoded",
        }
        # Try SDK first, fall back to raw HTTP
        try:
            from kiteconnect import KiteConnect
            self._kite = KiteConnect(api_key=api_key)
            self._kite.set_access_token(access_token)
            self._use_sdk = True
        except ImportError:
            self._kite    = None
            self._use_sdk = False
            logger.warning("kiteconnect SDK not installed — using raw HTTP")

    def _get(self, path, params=None):
        import requests as req
        r = req.get(self.BASE + path, params=params,
                    headers=self._headers, timeout=15)
        return r.json()

    def _post(self, path, data=None):
        import requests as req
        r = req.post(self.BASE + path, data=data,
                     headers=self._headers, timeout=15)
        return r.json()

    def _delete(self, path, data=None):
        import requests as req
        r = req.delete(self.BASE + path, data=data,
                       headers=self._headers, timeout=15)
        return r.json()

    # ── PROFILE ──────────────────────────────────────────────
    def get_profile(self) -> dict:
        if self._use_sdk:
            try:
                return {"s": "ok", "data": self._kite.profile()}
            except Exception as e:
                return {"s": "error", "message": str(e)}
        return self._get("/user/profile")

    def get_funds(self) -> dict:
        if self._use_sdk:
            try:
                return {"s": "ok", "data": self._kite.margins()}
            except Exception as e:
                return {"s": "error", "message": str(e)}
        return self._get("/user/margins")

    def get_positions(self) -> dict:
        if self._use_sdk:
            try:
                return {"s": "ok", "data": self._kite.positions()}
            except Exception as e:
                return {"s": "error", "message": str(e)}
        return self._get("/portfolio/positions")

    def get_orders(self) -> dict:
        if self._use_sdk:
            try:
                return {"s": "ok", "data": self._kite.orders()}
            except Exception as e:
                return {"s": "error", "message": str(e)}
        return self._get("/orders")

    # ── QUOTES ───────────────────────────────────────────────
    def get_quotes(self, symbols: list[str]) -> dict:
        """
        symbols: plain NSE symbols like ["RELIANCE", "TCS"]
        Returns dict: symbol -> normalized quote dict
        """
        kite_syms = [f"NSE:{s}" for s in symbols]
        try:
            if self._use_sdk:
                raw = self._kite.quote(kite_syms)
            else:
                resp = self._get("/quote", params={"i": kite_syms})
                if resp.get("status") == "error":
                    logger.error(f"Zerodha quote API error: {resp.get('message')}")
                    return {}
                raw = resp.get("data", {})

            if not raw:
                logger.warning(f"Zerodha get_quotes returned empty for: {symbols[:5]}")
                return {}

            result = {}
            for key, q in raw.items():
                sym        = key.replace("NSE:", "").replace("BSE:", "")
                ohlc       = q.get("ohlc", {})
                ltp        = float(q.get("last_price", 0))
                prev_close = float(ohlc.get("close", 0))
                # When market closed, ltp = 0, use prev close
                if ltp == 0:
                    ltp = prev_close
                pct = round((ltp - prev_close) / prev_close * 100, 2) if prev_close else 0
                result[sym] = {
                    "ltp":              ltp,
                    "open_price":       float(ohlc.get("open", 0)),
                    "high_price":       float(ohlc.get("high", 0)),
                    "low_price":        float(ohlc.get("low",  0)),
                    "prev_close_price": prev_close,
                    "chp":              pct,
                    "ch":               round(ltp - prev_close, 2),
                    "volume":           int(q.get("volume", 0)),
                    "buy_qty":          int(q.get("buy_quantity", 0)),
                    "sell_qty":         int(q.get("sell_quantity", 0)),
                }
            logger.info(f"Zerodha get_quotes: fetched {len(result)} symbols")
            return result
        except Exception as e:
            msg = str(e)
            if "permission" in msg.lower() or "403" in msg:
                logger.error(f"Zerodha get_quotes PERMISSION ERROR: {PERM_MSG}")
                return {"_permission_error": PERM_MSG}
            logger.error(f"Zerodha get_quotes error: {e}", exc_info=True)
            return {}

    def get_index_quotes(self) -> dict:
        """
        Zerodha index symbols (string format, not tokens):
        NSE:NIFTY 50, NSE:NIFTY BANK, NSE:NIFTY FIN SERVICE,
        NSE:NIFTY MIDCAP 50, BSE:SENSEX
        """
        index_syms = {
            "NIFTY 50":     "NSE:NIFTY 50",
            "BANK NIFTY":   "NSE:NIFTY BANK",
            "FIN NIFTY":    "NSE:NIFTY FIN SERVICE",
            "MIDCAP NIFTY": "NSE:NIFTY MIDCAP 50",
            "SENSEX":       "BSE:SENSEX",
        }
        try:
            sym_list = list(index_syms.values())
            if self._use_sdk:
                raw = self._kite.quote(sym_list)
            else:
                resp = self._get("/quote", params={"i": sym_list})
                if resp.get("status") == "error":
                    logger.error(f"Zerodha index quote API error: {resp.get('message')}")
                    return {}
                raw = resp.get("data", {})

            result = {}
            sym_to_name = {v: k for k, v in index_syms.items()}
            for key, q in raw.items():
                name = sym_to_name.get(key, key)
                ohlc = q.get("ohlc", {})
                ltp  = float(q.get("last_price", 0))
                prev = float(ohlc.get("close", 0))
                pct  = round((ltp - prev) / prev * 100, 2) if prev else 0
                result[name] = {
                    "ltp": ltp,
                    "chp": pct,
                    "ch":  round(ltp - prev, 2),
                }
            logger.info(f"Zerodha index quotes fetched: {list(result.keys())}")
            return result
        except Exception as e:
            msg = str(e)
            if "permission" in msg.lower() or "403" in msg:
                logger.error(f"Zerodha index quotes PERMISSION ERROR: {PERM_MSG}")
            else:
                logger.error(f"Zerodha index quotes error: {e}")
            return {}

    # ── HISTORICAL ───────────────────────────────────────────
    def get_historical(self, symbol: str, resolution: str = "day",
                       from_date: str = None, to_date: str = None) -> dict:
        """
        resolution: minute, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute, day
        Returns same format as Fyers: {s, t, o, h, l, c, v}
        """
        now = datetime.now()
        if not to_date:
            to_date   = now.strftime("%Y-%m-%d")
        if not from_date:
            from_date = (now - timedelta(days=100)).strftime("%Y-%m-%d")

        try:
            # Need instrument_token for historical — fetch via quote
            quote_resp = self.get_quotes([symbol])
            # Fallback: get token from instruments list
            instrument_token = self._get_instrument_token(symbol)
            if not instrument_token:
                return {"s": "error", "message": f"No instrument token for {symbol}"}

            if self._use_sdk:
                candles = self._kite.historical_data(
                    instrument_token, from_date, to_date, resolution
                )
            else:
                resp    = self._get(
                    f"/instruments/historical/{instrument_token}/{resolution}",
                    params={"from": from_date, "to": to_date}
                )
                candles = resp.get("data", {}).get("candles", [])

            # Normalize to {s, t, o, h, l, c, v}
            if not candles:
                return {"s": "error", "message": "No candles returned"}

            result = {"s": "ok", "t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
            for c in candles:
                if isinstance(c, dict):
                    # SDK returns dicts
                    ts = c["date"]
                    result["t"].append(int(ts.timestamp()) if hasattr(ts, "timestamp") else int(ts))
                    result["o"].append(float(c["open"]))
                    result["h"].append(float(c["high"]))
                    result["l"].append(float(c["low"]))
                    result["c"].append(float(c["close"]))
                    result["v"].append(int(c["volume"]))
                else:
                    # Raw API returns lists
                    from datetime import datetime as dt
                    ts_str = c[0]
                    try:
                        ts = dt.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                        result["t"].append(int(ts.timestamp()))
                    except Exception:
                        result["t"].append(0)
                    result["o"].append(float(c[1]))
                    result["h"].append(float(c[2]))
                    result["l"].append(float(c[3]))
                    result["c"].append(float(c[4]))
                    result["v"].append(int(c[5]))
            return result

        except Exception as e:
            msg = str(e)
            if "permission" in msg.lower() or "403" in msg or "Forbidden" in msg:
                msg = ("Insufficient permission: Enable 'Historical Data' permission "
                       "at developers.kite.trade → your app → Edit → check Historical Data")
            logger.error(f"Zerodha get_historical error for {symbol}: {msg}")
            return {"s": "error", "message": msg}

    def _get_instrument_token(self, symbol: str) -> int | None:
        """Look up instrument token — uses hardcoded map first, falls back to API."""
        # Fast path: use pre-built token map (avoids 3MB CSV download)
        token = ZD_INSTRUMENT_TOKENS.get(symbol)
        if token:
            return token
        # Slow path: download instruments list (only for unknown symbols)
        try:
            logger.warning(f"Token not in cache for {symbol}, downloading instruments...")
            if self._use_sdk:
                instruments = self._kite.instruments("NSE")
            else:
                resp        = self._get("/instruments/NSE")
                instruments = resp if isinstance(resp, list) else []
            for inst in instruments:
                if inst.get("tradingsymbol") == symbol:
                    return inst["instrument_token"]
        except Exception as e:
            logger.error(f"Instrument token lookup failed: {e}")
        return None

    # ── ORDERS ───────────────────────────────────────────────
    def place_order(self, symbol: str, side: str, qty: int,
                    order_type: str = "MARKET", limit_price: float = 0.0,
                    product_type: str = "MIS",
                    stop_loss: float = 0.0, take_profit: float = 0.0) -> dict:
        """
        side: BUY | SELL
        order_type: MARKET | LIMIT | SL | SL-M
        product_type: MIS (intraday) | CNC (delivery) | NRML (F&O)
        """
        # Zerodha product type mapping
        product_map = {
            "INTRADAY": "MIS", "CNC": "CNC",
            "MARGIN": "NRML", "MIS": "MIS", "NRML": "NRML"
        }
        # Order type mapping
        type_map = {
            "MARKET": "MARKET", "LIMIT": "LIMIT",
            "STOP": "SL-M",     "STOP-LIMIT": "SL"
        }
        kite_product = product_map.get(product_type.upper(), "MIS")
        kite_type    = type_map.get(order_type.upper(), "MARKET")
        kite_side    = "BUY" if side.upper() == "BUY" else "SELL"

        try:
            if self._use_sdk:
                from kiteconnect import KiteConnect
                order_id = self._kite.place_order(
                    variety   = KiteConnect.VARIETY_REGULAR,
                    exchange  = "NSE",
                    tradingsymbol = symbol,
                    transaction_type = kite_side,
                    quantity  = qty,
                    product   = kite_product,
                    order_type= kite_type,
                    price     = limit_price if kite_type == "LIMIT" else None,
                    trigger_price = stop_loss if kite_type in ("SL", "SL-M") else None,
                )
                return {"s": "ok", "id": str(order_id), "message": "Order placed"}
            else:
                data = {
                    "exchange":         "NSE",
                    "tradingsymbol":    symbol,
                    "transaction_type": kite_side,
                    "quantity":         qty,
                    "product":          kite_product,
                    "order_type":       kite_type,
                    "variety":          "regular",
                }
                if kite_type == "LIMIT":
                    data["price"] = limit_price
                if kite_type in ("SL", "SL-M") and stop_loss:
                    data["trigger_price"] = stop_loss
                resp = self._post("/orders/regular", data=data)
                if resp.get("status") == "success":
                    return {"s": "ok", "id": str(resp["data"]["order_id"]),
                            "message": "Order placed"}
                return {"s": "error", "message": resp.get("message", "Unknown error")}
        except Exception as e:
            logger.error(f"Zerodha place_order error: {e}")
            return {"s": "error", "message": str(e)}

    def cancel_order(self, order_id: str) -> dict:
        try:
            if self._use_sdk:
                from kiteconnect import KiteConnect
                self._kite.cancel_order(KiteConnect.VARIETY_REGULAR, order_id)
                return {"s": "ok"}
            return self._delete(f"/orders/regular/{order_id}")
        except Exception as e:
            return {"s": "error", "message": str(e)}
