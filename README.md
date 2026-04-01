# 🚀 VYAPAAR — Professional F&O Trading Terminal

> Python · Flask · Fyers API v3 · PostgreSQL (Render) · SuperTrend · APScheduler

---

## ✅ FEATURE OVERVIEW

| Feature | Status |
|---|---|
| User Registration / Login (PostgreSQL) | ✅ |
| Fyers OAuth Connect (App ID + Secret) | ✅ |
| Live Indices: Nifty 50, BankNifty, FinNifty, Midcap, Sensex | ✅ |
| Real-time F&O quotes (50 stocks batch) | ✅ |
| Top 5 / Top 10 Gainers & Losers Scanner | ✅ |
| SuperTrend Indicator (configurable Period/Multiplier) | ✅ |
| RSI + EMA Crossover confirmation | ✅ |
| Monte Carlo P&L Probability | ✅ |
| Stop Loss + Take Profit (Risk:Reward) | ✅ |
| Single Order Placement with confirmation modal | ✅ |
| Bulk Equal Allocation (Top 5 → equal funds) | ✅ |
| APScheduler — schedule jobs for next day | ✅ |
| Recurring daily jobs | ✅ |
| Trade history stored in PostgreSQL | ✅ |
| Open Positions + Today's Orders | ✅ |

---

## 📦 SETUP INSTRUCTIONS

### 1. Clone / download this project

```bash
cd vyapaar
```

### 2. Create a Python virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your `.env` file

```bash
cp .env.example .env
```

Edit `.env`:
```
SECRET_KEY=your-super-secret-flask-key-change-this
DATABASE_URL=postgresql://user:pass@host:5432/metadataloop_db
APP_BASE_URL=http://localhost:5000
FYERS_REDIRECT_URI=http://localhost:5000/fyers/callback
```

**Get your DATABASE_URL from Render:**
- Go to your Render dashboard → `metadataloop_db` → Connection → External URL

---

### 5. Run DB migrations in DBeaver

Open DBeaver → connect to `metadataloop_db` → open `db/migrations.sql` → Execute All

This creates 4 tables:
- `vyapaar_users`
- `fyers_credentials`
- `vyapaar_scheduled_jobs`
- `vyapaar_trade_history`

---

### 6. Start the server

```bash
python app.py
```

Open: `http://localhost:5000`

---

## 🔐 FYERS API SETUP (Step-by-Step)

### Step 1 — Create Fyers API App
1. Go to **https://myapi.fyers.in**
2. Login with your Fyers trading account
3. Click **Dashboard** → **Create App**
4. Fill in:
   - **App Name**: VYAPAAR (or anything)
   - **Redirect URL**: `http://localhost:5000/fyers/callback`
   - **Permissions**: ✅ Market Data, ✅ Order Placement, ✅ Portfolio, ✅ Holdings
5. Submit → Wait for approval (usually instant for personal apps)

### Step 2 — Get App ID and Secret Key
After creation:
- **App ID (Client ID)**: e.g. `XJ12345-100`
- **Secret Key**: long alphanumeric string

### Step 3 — Daily Token Flow
Fyers tokens expire **every day at midnight IST**.

Each morning before trading:
1. Go to `/fyers/setup` in the app
2. Click **Connect Fyers (Login)**
3. Login to Fyers in the browser
4. You'll be redirected back with token auto-saved ✅

### What Redirect URL to use?

| Scenario | Redirect URL |
|---|---|
| Running locally | `http://localhost:5000/fyers/callback` |
| Deployed on Render/Railway | `https://yourdomain.onrender.com/fyers/callback` |
| No server (quick test) | `https://trade.fyers.in/api-login/redirect-uri/index.html` |

---

## 🧠 SUPERTREND STRATEGY

### How SuperTrend works
- Computes **ATR** (Average True Range) over N periods
- Creates upper/lower bands: `HL2 ± (Multiplier × ATR)`
- **BUY signal**: Price crosses above SuperTrend line
- **SELL signal**: Price crosses below SuperTrend line

### Additional filters used
- **RSI (14)**: Confirms overbought/oversold
- **EMA crossover** (9/21): Trend confirmation
- **Volume ratio**: High volume = stronger signal
- **Monte Carlo**: 1000 simulations on historical returns to compute P&L probability

### Default settings
- Period: 10, Multiplier: 3.0 (industry standard for intraday)
- Stop Loss: SuperTrend line (natural level)
- Take Profit: 2× the risk (1:2 Risk:Reward)

---

## ⏱ SCHEDULER

The scheduler uses **APScheduler** running in background threads.

### How a job runs (e.g. 9:25 AM)
1. Server checks for Fyers token validity
2. Calls `/api/scan` → fetches all 50 F&O stocks
3. Ranks by % gain since open (9:15–9:25)
4. Runs SuperTrend on top N gainers
5. Filters only those with **BUY signal**
6. Divides allocated funds equally
7. Places MARKET orders with SL at ST line
8. Records everything in `vyapaar_trade_history`

### ⚠ Important
- Server must be **running** when job fires
- Token must be **valid** (log in each morning)
- For production, deploy on Render with gunicorn

---

## 🗄️ DATABASE TABLES

```sql
vyapaar_users          -- App users (email, username, password_hash)
fyers_credentials      -- Per-user Fyers app_id, secret, access_token
vyapaar_scheduled_jobs -- Automation jobs with APScheduler
vyapaar_trade_history  -- All orders placed (manual + automated)
```

---

## 🚀 PRODUCTION DEPLOYMENT (Render)

1. Push to GitHub
2. Create a **Web Service** on Render
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
5. Add environment variables from `.env`
6. Update `FYERS_REDIRECT_URI` to `https://your-app.onrender.com/fyers/callback`
7. Update the redirect URL in your Fyers app settings

---

## 📁 PROJECT STRUCTURE

```
vyapaar/
├── app.py                    # Flask app entry point
├── config.py                 # Config from .env
├── requirements.txt
├── .env.example
├── db/
│   ├── models.py             # SQLAlchemy models
│   └── migrations.sql        # Run in DBeaver
├── routes/
│   ├── auth.py               # Register, Login, Logout
│   ├── fyers_auth.py         # Fyers OAuth connect
│   └── trading.py            # All trading APIs
├── services/
│   ├── fyers_client.py       # Fyers API v3 wrapper
│   ├── supertrend.py         # SuperTrend + RSI + Monte Carlo
│   ├── scanner.py            # F&O universe scanner
│   └── scheduler.py          # APScheduler job runner
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── fyers_setup.html      # HOW-TO guide + credentials
    ├── fyers_token.html
    ├── dashboard.html        # Main terminal
    └── scheduler.html        # Job scheduler UI
```
