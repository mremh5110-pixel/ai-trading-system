"""
data_feed/mt5_connector.py
============================
اتصال ببيانات MetaTrader 5 الحقيقية.

⚠️ متطلبات مهمة:
- مكتبة MetaTrader5 الرسمية تعمل فقط على Windows، ولازم تكون منصة MT5
  (Terminal) مثبّتة ومسجّل دخولها على حسابك (ديمو أو حقيقي) على نفس الجهاز.
- شغّل هذا الملف على نفس جهاز الويندوز اللي فيه MT5، مش على سيرفر Linux.

لو حابب تشغّل النظام على سيرفر Linux/VPS: البديل الشائع هو تشغيل MT5 داخل
Wine، أو استخدام حساب Broker يوفر REST/WebSocket API مباشرة بدل MT5.
"""
from datetime import datetime
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def connect(login: int = None, password: str = None, server: str = None) -> bool:
    if not MT5_AVAILABLE:
        raise RuntimeError("مكتبة MetaTrader5 غير متوفرة. شغّل هذا الملف على Windows مع تثبيت MT5.")
    if not mt5.initialize():
        raise RuntimeError(f"فشل تهيئة MT5: {mt5.last_error()}")
    if login and password and server:
        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            raise RuntimeError(f"فشل تسجيل الدخول لحساب MT5: {mt5.last_error()}")
    return True


def fetch_ohlc(symbol: str, timeframe: str, num_bars: int = 500) -> pd.DataFrame:
    if not MT5_AVAILABLE:
        raise RuntimeError("مكتبة MetaTrader5 غير متوفرة على هذه البيئة.")
    tf_const = getattr(mt5, TIMEFRAME_MAP[timeframe])
    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, num_bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"لم يتم استلام بيانات للرمز {symbol} على فريم {timeframe}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["open", "high", "low", "close", "volume"]]


def fetch_multi_timeframe(symbol: str, timeframes: list, num_bars: int = 500) -> dict:
    return {tf: fetch_ohlc(symbol, tf, num_bars) for tf in timeframes}


def shutdown():
    if MT5_AVAILABLE:
        mt5.shutdown()


# ---------------------------------------------------------------------------
# وضع تجريبي (Demo/Offline mode) - يولّد بيانات صناعية واقعية الشكل عشان تقدر
# تختبر باقي النظام بدون MT5 حقيقي متصل (مفيد للتطوير على Linux/Mac).
# ---------------------------------------------------------------------------
def generate_demo_ohlc(num_bars: int = 500, start_price: float = 2350.0, freq: str = "15min",
                        seed: int = 42, end: datetime = None) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1, num_bars).cumsum() * 0.6
    close = start_price + steps
    idx = pd.date_range(end=end or datetime.utcnow(), periods=num_bars, freq=freq)

    high = close + rng.uniform(0.3, 2.0, num_bars)
    low = close - rng.uniform(0.3, 2.0, num_bars)
    open_ = close + rng.uniform(-1.0, 1.0, num_bars)
    volume = rng.integers(100, 5000, num_bars)

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def generate_demo_multi_timeframe(timeframes: list, num_bars: int = 500, seed_offset: int = 0, end: datetime = None) -> dict:
    freq_map = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h", "D1": "1D"}
    end = end or datetime.utcnow()
    return {tf: generate_demo_ohlc(num_bars, freq=freq_map.get(tf, "15min"),
                                    seed=(hash(tf) + seed_offset) % 100000, end=end)
            for tf in timeframes}
