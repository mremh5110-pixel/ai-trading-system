"""
indicators/technical.py
========================
تنفيذ حقيقي (مش مكتبة جاهزة) للمؤشرات الكلاسيكية الأكثر استخدامًا.
كل الدوال تستقبل DataFrame فيه الأعمدة: open, high, low, close, volume (اختياري)
وترجع Series أو DataFrame بنفس الطول.
"""
import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger_bands(close: pd.Series, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower})


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = atr(df, period) * period  # true range base (un-smoothed reconstruction)
    plus_dm_s = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()
    minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()
    atr_s = atr(df, period).replace(0, np.nan)

    plus_di = 100 * (plus_dm_s / atr_s)
    minus_di = 100 * (minus_dm_s / atr_s)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0)


def vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP تراكمي يُعاد ضبطه يوميًا (يتطلب index من نوع datetime)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)
    day = df.index.date if isinstance(df.index, pd.DatetimeIndex) else np.zeros(len(df))
    grouped = pd.DataFrame({"tp_vol": typical_price * vol, "vol": vol, "day": day})
    cum_tp_vol = grouped.groupby("day")["tp_vol"].cumsum()
    cum_vol = grouped.groupby("day")["vol"].cumsum().replace(0, np.nan)
    return (cum_tp_vol / cum_vol).ffill()


def moving_averages(close: pd.Series, periods=(20, 50, 200)) -> pd.DataFrame:
    return pd.DataFrame({f"ma_{p}": ema(close, p) for p in periods})


def compute_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """يحسب كل المؤشرات ويرجعها مدموجة مع df الأصلي (نسخة جديدة)."""
    out = df.copy()
    out["rsi"] = rsi(out["close"], cfg.RSI_PERIOD)
    macd_df = macd(out["close"], cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    out = out.join(macd_df)
    out["atr"] = atr(out, cfg.ATR_PERIOD)
    bb_df = bollinger_bands(out["close"], cfg.BB_PERIOD, cfg.BB_STD)
    out = out.join(bb_df)
    out["adx"] = adx(out, cfg.ADX_PERIOD)
    ma_df = moving_averages(out["close"], cfg.MA_PERIODS)
    out = out.join(ma_df)
    if isinstance(out.index, pd.DatetimeIndex):
        out["vwap"] = vwap(out)
    return out
