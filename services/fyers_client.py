"""
Fyers API v3 Client Wrapper
Handles auth URL generation, token exchange, and all trading API calls.
"""
import logging
from datetime import datetime, timedelta
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws

logger = logging.getLogger(__name__)

# ── F&O universe with lot sizes ──────────────────────────────
FO_STOCKS = [
    {"sym": "RELIANCE",    "lot": 250,  "name": "Reliance Industries"},
    {"sym": "TCS",         "lot": 150,  "name": "Tata Consultancy Services"},
    {"sym": "INFY",        "lot": 300,  "name": "Infosys Ltd"},
    {"sym": "HDFCBANK",    "lot": 550,  "name": "HDFC Bank"},
    {"sym": "ICICIBANK",   "lot": 700,  "name": "ICICI Bank"},
    {"sym": "SBIN",        "lot": 1500, "name": "State Bank of India"},
    {"sym": "BAJFINANCE",  "lot": 125,  "name": "Bajaj Finance"},
    {"sym": "KOTAKBANK",   "lot": 400,  "name": "Kotak Mahindra Bank"},
    {"sym": "LT",          "lot": 175,  "name": "Larsen & Toubro"},
    {"sym": "AXISBANK",    "lot": 625,  "name": "Axis Bank"},
    {"sym": "WIPRO",       "lot": 1500, "name": "Wipro Ltd"},
    {"sym": "MARUTI",      "lot": 100,  "name": "Maruti Suzuki"},
    {"sym": "TATAMOTORS",  "lot": 550,  "name": "Tata Motors"},
    {"sym": "TECHM",       "lot": 600,  "name": "Tech Mahindra"},
    {"sym": "SUNPHARMA",   "lot": 350,  "name": "Sun Pharmaceutical"},
    {"sym": "DRREDDY",     "lot": 125,  "name": "Dr. Reddys Lab"},
    {"sym": "BHARTIARTL",  "lot": 950,  "name": "Bharti Airtel"},
    {"sym": "NTPC",        "lot": 3000, "name": "NTPC Ltd"},
    {"sym": "ONGC",        "lot": 1925, "name": "Oil & Natural Gas"},
    {"sym": "ADANIPORTS",  "lot": 1250, "name": "Adani Ports"},
    {"sym": "TATASTEEL",   "lot": 5500, "name": "Tata Steel"},
    {"sym": "HINDALCO",    "lot": 2150, "name": "Hindalco Industries"},
    {"sym": "JSWSTEEL",    "lot": 1350, "name": "JSW Steel"},
    {"sym": "BAJAJ-AUTO",  "lot": 250,  "name": "Bajaj Auto"},
    {"sym": "INDUSINDBK",  "lot": 500,  "name": "IndusInd Bank"},
    {"sym": "HCLTECH",     "lot": 700,  "name": "HCL Technologies"},
    {"sym": "DIVISLAB",    "lot": 200,  "name": "Divis Laboratories"},
    {"sym": "ASIANPAINT",  "lot": 300,  "name": "Asian Paints"},
    {"sym": "TITAN",       "lot": 375,  "name": "Titan Company"},
    {"sym": "GRASIM",      "lot": 475,  "name": "Grasim Industries"},
    {"sym": "POWERGRID",   "lot": 2700, "name": "Power Grid Corp"},
    {"sym": "COALINDIA",   "lot": 4200, "name": "Coal India"},
    {"sym": "ULTRACEMCO",  "lot": 100,  "name": "UltraTech Cement"},
    {"sym": "CHOLAFIN",    "lot": 1250, "name": "Cholamandalam Inv"},
    {"sym": "SBILIFE",     "lot": 750,  "name": "SBI Life Insurance"},
    {"sym": "HDFCLIFE",    "lot": 1100, "name": "HDFC Life Insurance"},
    {"sym": "NAUKRI",      "lot": 125,  "name": "Info Edge"},
    {"sym": "MPHASIS",     "lot": 400,  "name": "Mphasis Ltd"},
    {"sym": "PERSISTENT",  "lot": 250,  "name": "Persistent Systems"},
    {"sym": "LTIM",        "lot": 150,  "name": "LTIMindtree"},
    {"sym": "BANKBARODA",  "lot": 5850, "name": "Bank of Baroda"},
    {"sym": "CANBK",       "lot": 1875, "name": "Canara Bank"},
    {"sym": "PNB",         "lot": 8000, "name": "Punjab National Bank"},
    {"sym": "CIPLA",       "lot": 650,  "name": "Cipla Ltd"},
    {"sym": "HEROMOTOCO",  "lot": 300,  "name": "Hero MotoCorp"},
    {"sym": "EICHERMOT",   "lot": 175,  "name": "Eicher Motors"},
    {"sym": "M&M",         "lot": 700,  "name": "Mahindra & Mahindra"},
    {"sym": "VEDL",        "lot": 4100, "name": "Vedanta Ltd"},
    {"sym": "AMBUJACEM",   "lot": 1500, "name": "Ambuja Cements"},
    {"sym": "ICICIPRULI",  "lot": 1500, "name": "ICICI Prudential Life"},
]

FO_MAP = {s["sym"]: s for s in FO_STOCKS}

INDICES = {
    "NIFTY 50":      "NSE:NIFTY50-INDEX",
    "BANK NIFTY":    "NSE:NIFTYBANK-INDEX",
    "FIN NIFTY":     "NSE:NIFTYFIN-INDEX",
    "MIDCAP NIFTY":  "NSE:NIFTYMIDCAP50-INDEX",
    "SENSEX":        "BSE:SENSEX-INDEX",
}


class FyersClient:
    """Wraps fyers-apiv3 for a single user's session."""

    def __init__(self, app_id: str, access_token: str):
        self.app_id = app_id
        self.access_token = access_token
        self._fyers = fyersModel.FyersModel(
            client_id=app_id,
            token=access_token,
            log_path="",
            is_async=False,
        )

    # ── PROFILE ──────────────────────────────────────────────
    def get_profile(self):
        return self._fyers.get_profile()

    def get_funds(self):
        return self._fyers.funds()

    def get_positions(self):
        return self._fyers.positions()

    def get_orders(self):
        return self._fyers.orderbook()

    def get_trades_today(self):
        return self._fyers.tradebook()

    # ── QUOTES ───────────────────────────────────────────────
    def get_quotes(self, symbols: list[str]) -> dict:
        """
        symbols: plain NSE symbols like ["RELIANCE", "TCS"]
        Returns dict: symbol -> quote dict
        """
        fyers_syms = ",".join(f"NSE:{s}-EQ" for s in symbols)
        resp = self._fyers.quotes({"symbols": fyers_syms})
        result = {}
        if resp and resp.get("s") == "ok":
            for q in resp.get("d", []):
                raw = q.get("n", "")
                sym = raw.replace("NSE:", "").replace("-EQ", "")
                result[sym] = q.get("v", {})
        return result

    def get_index_quotes(self) -> dict:
        syms = ",".join(INDICES.values())
        resp = self._fyers.quotes({"symbols": syms})
        result = {}
        if resp and resp.get("s") == "ok":
            for q in resp.get("d", []):
                v = q.get("v", {})
                name_map = {v2: k for k, v2 in INDICES.items()}
                sym_key = name_map.get(q.get("n", ""), q.get("n", ""))
                result[sym_key] = v
        return result

    # ── HISTORICAL ───────────────────────────────────────────
    def get_historical(self, symbol: str, resolution: str = "D",
                       from_date: str = None, to_date: str = None) -> dict:
        """
        resolution: 1,2,3,5,10,15,20,30,60,120,240,D,W,M
        from_date/to_date: "YYYY-MM-DD"
        """
        now = datetime.now()
        if not to_date:
            to_date = now.strftime("%Y-%m-%d")
        if not from_date:
            from_date = (now - timedelta(days=100)).strftime("%Y-%m-%d")

        # convert to epoch
        from_ts = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp())
        to_ts   = int(datetime.strptime(to_date,   "%Y-%m-%d").timestamp())

        data = {
            "symbol": f"NSE:{symbol}-EQ",
            "resolution": resolution,
            "date_format": "0",
            "range_from": str(from_ts),
            "range_to":   str(to_ts),
            "cont_flag":  "1",
        }
        raw = self._fyers.history(data)

        # ── Fyers v3 returns candles as list-of-lists ──────────
        # [[epoch, open, high, low, close, volume], ...]
        # Convert to t/o/h/l/c/v dict so supertrend.analyse() works
        if raw and raw.get("s") == "ok" and "candles" in raw:
            candles = raw["candles"]
            raw["t"] = [c[0] for c in candles]
            raw["o"] = [c[1] for c in candles]
            raw["h"] = [c[2] for c in candles]
            raw["l"] = [c[3] for c in candles]
            raw["c"] = [c[4] for c in candles]
            raw["v"] = [c[5] for c in candles]
        return raw

    # ── ORDERS ───────────────────────────────────────────────
    def place_order(self, symbol: str, side: str, qty: int,
                    order_type: str = "MARKET", limit_price: float = 0.0,
                    product_type: str = "INTRADAY",
                    stop_loss: float = 0.0, take_profit: float = 0.0) -> dict:
        """
        side: BUY | SELL
        order_type: MARKET | LIMIT | STOP | STOP-LIMIT
        product_type: INTRADAY | CNC | MARGIN | CO | BO
        """
        side_map = {"BUY": 1, "SELL": -1}
        type_map = {"MARKET": 2, "LIMIT": 1, "STOP": 3, "STOP-LIMIT": 4}

        order = {
            "symbol":        f"NSE:{symbol}-EQ",
            "qty":           qty,
            "type":          type_map.get(order_type, 2),
            "side":          side_map.get(side, 1),
            "productType":   product_type,
            "limitPrice":    limit_price,
            "stopPrice":     stop_loss,
            "validity":      "DAY",
            "disclosedQty":  0,
            "offlineOrder":  False,
            "stopLoss":      stop_loss,
            "takeProfit":    take_profit,
        }
        return self._fyers.place_order(order)

    def cancel_order(self, order_id: str) -> dict:
        return self._fyers.cancel_order({"id": order_id})

    def modify_order(self, order_id: str, qty: int = None,
                     limit_price: float = None) -> dict:
        data = {"id": order_id}
        if qty:         data["qty"]        = qty
        if limit_price: data["limitPrice"] = limit_price
        return self._fyers.modify_order(data)

    # ── BULK ORDERS ──────────────────────────────────────────
    def place_bulk_orders(self, orders: list[dict]) -> list[dict]:
        """
        orders: list of {symbol, side, qty, order_type, product_type}
        Returns list of results.
        """
        results = []
        for o in orders:
            r = self.place_order(
                symbol=o["symbol"],
                side=o["side"],
                qty=o["qty"],
                order_type=o.get("order_type", "MARKET"),
                product_type=o.get("product_type", "INTRADAY"),
                stop_loss=o.get("stop_loss", 0),
                take_profit=o.get("take_profit", 0),
            )
            results.append({"symbol": o["symbol"], "result": r})
        return results


# ── AUTH HELPER (stateless, before login) ────────────────────
def generate_auth_url(app_id: str, redirect_uri: str) -> str:
    """
    Build Fyers OAuth2 login URL directly (avoids SessionModel quirks in v3).
    Format: https://api-t1.fyers.in/api/v3/generate-authcode?client_id=...
    """
    from urllib.parse import urlencode, quote_plus
    base = "https://api-t1.fyers.in/api/v3/generate-authcode"
    params = urlencode({
        "client_id":     app_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "state":         "vyapaar",
    }, quote_via=quote_plus)
    return f"{base}?{params}"


def exchange_auth_code(app_id: str, secret_key: str,
                       auth_code: str,
                       redirect_uri: str = "https://trade.fyers.in/api-login/redirect-uri/index.html") -> dict:
    """
    Exchange auth_code for access_token using direct HTTPS call.
    redirect_uri MUST exactly match what was registered in the Fyers app.
    """
    import hashlib
    import requests as req
    app_hash = hashlib.sha256(f"{app_id}:{secret_key}".encode()).hexdigest()
    payload = {
        "grant_type":  "authorization_code",
        "appIdHash":   app_hash,
        "code":        auth_code,
    }
    resp = req.post(
        "https://api-t1.fyers.in/api/v3/validate-authcode",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    return resp.json()
