"""
SuperTrend Indicator + Advanced Signal Engine
─────────────────────────────────────────────
SuperTrend(period=10, multiplier=3) is the default.
Also computes: RSI, EMA crossover, volume confirmation,
P&L probability via historical volatility Monte Carlo.
"""
import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── DATA CLASSES ─────────────────────────────────────────────
@dataclass
class SuperTrendResult:
    symbol:         str
    signal:         str           # BUY | SELL | HOLD
    confidence:     float         # 0-100 %
    supertrend_val: float
    current_price:  float
    atr:            float
    rsi:            float
    ema_short:      float
    ema_long:       float
    volume_ratio:   float         # current vol / avg vol
    stop_loss:      float
    take_profit:    float
    risk_reward:    float
    pl_probability: float         # % chance of profit (Monte Carlo)
    reasons:        list = field(default_factory=list)
    raw_df:         Optional[pd.DataFrame] = field(default=None, repr=False)


# ── SUPERTREND CORE ──────────────────────────────────────────
def compute_atr(df: pd.DataFrame, period: int = 10) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def compute_supertrend(df: pd.DataFrame, period: int = 10,
                       multiplier: float = 3.0) -> pd.DataFrame:
    df = df.copy()
    hl2 = (df["high"] + df["low"]) / 2
    atr = compute_atr(df, period)

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=int)   # 1=up(BUY), -1=down(SELL)

    for i in range(1, len(df)):
        close = df["close"].iloc[i]
        prev_close = df["close"].iloc[i - 1]
        prev_upper = upper_band.iloc[i - 1]
        prev_lower = lower_band.iloc[i - 1]
        prev_st    = supertrend.iloc[i - 1] if i > 1 else lower_band.iloc[0]
        prev_dir   = direction.iloc[i - 1]  if i > 1 else 1

        # Adjust bands
        cur_upper = upper_band.iloc[i]
        cur_lower = lower_band.iloc[i]
        if cur_upper > prev_upper or prev_close > prev_upper:
            final_upper = cur_upper
        else:
            final_upper = prev_upper
        upper_band.iloc[i] = final_upper

        if cur_lower < prev_lower or prev_close < prev_lower:
            final_lower = cur_lower
        else:
            final_lower = prev_lower
        lower_band.iloc[i] = final_lower

        # Determine trend direction
        if prev_st == prev_upper:
            if close <= final_upper:
                supertrend.iloc[i] = final_upper
                direction.iloc[i]  = -1
            else:
                supertrend.iloc[i] = final_lower
                direction.iloc[i]  = 1
        else:
            if close >= final_lower:
                supertrend.iloc[i] = final_lower
                direction.iloc[i]  = 1
            else:
                supertrend.iloc[i] = final_upper
                direction.iloc[i]  = -1

    df["supertrend"]   = supertrend
    df["st_direction"] = direction
    df["atr"]          = atr
    df["upper_band"]   = upper_band
    df["lower_band"]   = lower_band
    return df


# ── ADDITIONAL INDICATORS ────────────────────────────────────
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def compute_ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


# ── MONTE CARLO P&L PROBABILITY ──────────────────────────────
def monte_carlo_probability(returns: pd.Series, side: str,
                             horizon_days: int = 1,
                             simulations: int = 1000) -> float:
    """
    Returns probability (0-100) that a trade in `side` direction
    will be profitable over `horizon_days`.
    Uses historical return distribution.
    """
    if len(returns) < 10:
        return 50.0
    mu  = returns.mean()
    sig = returns.std()
    if sig == 0:
        return 50.0
    rng = np.random.default_rng(42)
    sim = rng.normal(mu, sig, size=(simulations, horizon_days)).sum(axis=1)
    if side == "BUY":
        prob = (sim > 0).mean() * 100
    else:
        prob = (sim < 0).mean() * 100
    return round(float(prob), 1)


# ── FULL ANALYSIS ────────────────────────────────────────────
def analyse(symbol: str, ohlcv: dict,
            st_period: int = 10, st_mult: float = 3.0,
            ema_short: int = 9, ema_long: int = 21) -> SuperTrendResult:
    """
    ohlcv: Fyers history response dict with keys t, o, h, l, c, v
    Returns SuperTrendResult with full signal analysis.
    """
    try:
        df = pd.DataFrame({
            "date":  ohlcv["t"],
            "open":  ohlcv["o"],
            "high":  ohlcv["h"],
            "low":   ohlcv["l"],
            "close": ohlcv["c"],
            "volume":ohlcv["v"],
        })
        df["date"] = pd.to_datetime(df["date"], unit="s")
        df = df.sort_values("date").reset_index(drop=True)

        if len(df) < 20:
            raise ValueError("Not enough bars for analysis (need ≥20)")

        # Supertrend
        df = compute_supertrend(df, st_period, st_mult)

        # RSI
        df["rsi"] = compute_rsi(df["close"])

        # EMAs
        df["ema_s"] = compute_ema(df["close"], ema_short)
        df["ema_l"] = compute_ema(df["close"], ema_long)

        # Volume ratio (last vs 20-bar avg)
        df["vol_avg"] = df["volume"].rolling(20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        current_price = float(last["close"])
        st_val        = float(last["supertrend"])
        direction     = int(last["st_direction"])
        atr_val       = float(last["atr"])
        rsi_val       = float(last["rsi"])
        ema_s_val     = float(last["ema_s"])
        ema_l_val     = float(last["ema_l"])
        vol_ratio     = float(last["volume"] / last["vol_avg"]) if last["vol_avg"] > 0 else 1.0

        # ── SIGNAL LOGIC ──────────────────────────────────────
        reasons  = []
        score    = 0

        # 1. SuperTrend primary signal
        if direction == 1:
            score += 3
            reasons.append("✅ SuperTrend is BULLISH (price above ST line)")
        else:
            score -= 3
            reasons.append("🔴 SuperTrend is BEARISH (price below ST line)")

        # 2. SuperTrend cross (fresh signal = stronger)
        if direction != int(prev["st_direction"]):
            score += (2 if direction == 1 else -2)
            reasons.append("⚡ Fresh SuperTrend crossover detected!")

        # 3. RSI confirmation
        if rsi_val < 30:
            score += 2
            reasons.append(f"✅ RSI oversold ({rsi_val:.1f}) — potential reversal up")
        elif rsi_val > 70:
            score -= 2
            reasons.append(f"⚠️  RSI overbought ({rsi_val:.1f}) — caution on longs")
        elif 40 < rsi_val < 60:
            reasons.append(f"➡️  RSI neutral ({rsi_val:.1f})")
        else:
            reasons.append(f"RSI: {rsi_val:.1f}")

        # 4. EMA crossover
        if ema_s_val > ema_l_val:
            score += 1
            reasons.append(f"✅ EMA({ema_short}) > EMA({ema_long}) — bullish alignment")
        else:
            score -= 1
            reasons.append(f"🔴 EMA({ema_short}) < EMA({ema_long}) — bearish alignment")

        # 5. Volume confirmation
        if vol_ratio > 1.5:
            score += (1 if direction == 1 else -1)
            reasons.append(f"✅ Volume spike: {vol_ratio:.1f}x avg — strong conviction")
        elif vol_ratio < 0.7:
            reasons.append(f"⚠️  Low volume ({vol_ratio:.1f}x avg) — weak conviction")

        # ── FINAL SIGNAL ──────────────────────────────────────
        if score >= 3:
            signal = "BUY"
        elif score <= -3:
            signal = "SELL"
        else:
            signal = "HOLD"

        confidence = min(100.0, abs(score) / 7 * 100)

        # ── RISK MANAGEMENT ───────────────────────────────────
        if signal == "BUY":
            stop_loss   = st_val                              # ST line is natural SL
            take_profit = current_price + 2 * (current_price - stop_loss)  # 1:2 RR
        elif signal == "SELL":
            stop_loss   = st_val
            take_profit = current_price - 2 * (stop_loss - current_price)
        else:
            stop_loss   = current_price * 0.98
            take_profit = current_price * 1.02

        risk   = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        rr     = round(reward / risk, 2) if risk > 0 else 0.0

        # ── MONTE CARLO ───────────────────────────────────────
        daily_returns = df["close"].pct_change().dropna()
        pl_prob = monte_carlo_probability(daily_returns, signal)

        return SuperTrendResult(
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 1),
            supertrend_val=round(st_val, 2),
            current_price=round(current_price, 2),
            atr=round(atr_val, 2),
            rsi=round(rsi_val, 1),
            ema_short=round(ema_s_val, 2),
            ema_long=round(ema_l_val, 2),
            volume_ratio=round(vol_ratio, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_reward=rr,
            pl_probability=pl_prob,
            reasons=reasons,
            raw_df=df,
        )

    except Exception as e:
        logger.error(f"SuperTrend analysis failed for {symbol}: {e}")
        return SuperTrendResult(
            symbol=symbol, signal="HOLD", confidence=0,
            supertrend_val=0, current_price=0, atr=0,
            rsi=50, ema_short=0, ema_long=0, volume_ratio=1,
            stop_loss=0, take_profit=0, risk_reward=0,
            pl_probability=50.0, reasons=[f"Analysis error: {e}"],
        )


def result_to_dict(r: SuperTrendResult) -> dict:
    return {
        "symbol":         r.symbol,
        "signal":         r.signal,
        "confidence":     r.confidence,
        "supertrend_val": r.supertrend_val,
        "current_price":  r.current_price,
        "atr":            r.atr,
        "rsi":            r.rsi,
        "ema_short":      r.ema_short,
        "ema_long":       r.ema_long,
        "volume_ratio":   r.volume_ratio,
        "stop_loss":      r.stop_loss,
        "take_profit":    r.take_profit,
        "risk_reward":    r.risk_reward,
        "pl_probability": r.pl_probability,
        "reasons":        r.reasons,
    }
