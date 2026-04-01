-- ═══════════════════════════════════════════════════════════════
--  VYAPAAR — Database Migrations
--  Run this in DBeaver against your metadataloop_db on Render
--  Schema: public  (default)
-- ═══════════════════════════════════════════════════════════════

-- 1. USERS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vyapaar_users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255),
    phone         VARCHAR(20),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

-- 2. FYERS CREDENTIALS ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS fyers_credentials (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES vyapaar_users(id) ON DELETE CASCADE UNIQUE,
    app_id         VARCHAR(100)  NOT NULL,
    secret_key     VARCHAR(255)  NOT NULL,
    redirect_url   VARCHAR(500)  DEFAULT 'http://localhost:5000/fyers/callback',
    access_token   TEXT,
    refresh_token  TEXT,
    token_expiry   TIMESTAMP,
    fyers_user_id  VARCHAR(100),
    is_connected   BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

-- 3. SCHEDULED JOBS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vyapaar_scheduled_jobs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES vyapaar_users(id) ON DELETE CASCADE,
    job_name        VARCHAR(255) NOT NULL,
    strategy        VARCHAR(100) DEFAULT 'supertrend',
    symbols         JSONB,
    allocated_funds NUMERIC(15,2),
    top_n           INTEGER DEFAULT 5,
    order_type      VARCHAR(20)  DEFAULT 'MARKET',
    product_type    VARCHAR(20)  DEFAULT 'INTRADAY',
    scheduled_time  TIME NOT NULL,
    scheduled_date  DATE,
    is_recurring    BOOLEAN DEFAULT FALSE,
    status          VARCHAR(50)  DEFAULT 'pending',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    last_run        TIMESTAMP,
    next_run        TIMESTAMP
);

-- 4. TRADE HISTORY ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vyapaar_trade_history (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER REFERENCES vyapaar_users(id) ON DELETE CASCADE,
    symbol           VARCHAR(100) NOT NULL,
    exchange         VARCHAR(20)  DEFAULT 'NSE',
    order_type       VARCHAR(50),
    side             VARCHAR(10),
    quantity         INTEGER,
    price            NUMERIC(15,2),
    order_id         VARCHAR(255),
    status           VARCHAR(50),
    strategy         VARCHAR(100),
    signal_data      JSONB,
    pnl              NUMERIC(15,2),
    scheduled_job_id INTEGER REFERENCES vyapaar_scheduled_jobs(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT NOW(),
    filled_at        TIMESTAMP
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_fyers_user    ON fyers_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user     ON vyapaar_scheduled_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON vyapaar_scheduled_jobs(status);
CREATE INDEX IF NOT EXISTS idx_trades_user   ON vyapaar_trade_history(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON vyapaar_trade_history(symbol);

-- Verify
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'vyapaar%'
  OR  table_name = 'fyers_credentials'
ORDER BY table_name;
