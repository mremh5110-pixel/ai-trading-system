"""
data_feed/tradingview_feed.py
================================
يقرأ الشموع اللي وصلت عبر webhook/tradingview_webhook.py (سواء مخزّنة محليًا
أو في Firestore) ويحوّلها لنفس شكل DataFrame اللي يستخدمه باقي النظام
(open/high/low/close/volume + index زمني) - عشان signal_engine ما يفرقش
مصدر البيانات أصلًا.
"""
from typing import Optional
import pandas as pd

from storage.state_store import StateStore
from logging_setup.logger import get_logger

logger = get_logger(__name__)

TV_TIMEFRAME_MAP = {"M1": "1", "M5": "5", "M15": "15", "M30": "30", "H1": "60", "H4": "240", "D1": "D"}


def fetch_ohlc(store: StateStore, symbol: str, timeframe: str) -> pd.DataFrame:
    tv_tf = TV_TIMEFRAME_MAP.get(timeframe, timeframe)
    key = f"tv_{symbol}_{tv_tf}"
    data = store.get_signal(key)
    if not data or not data.get("candles"):
        raise RuntimeError(
            f"لا توجد بيانات TradingView مستلمة بعد للرمز {symbol} على فريم {timeframe}. "
            f"تأكد أن Alert مضبوط ومُفعّل في TradingView ويرسل لهذا الـ webhook."
        )
    df = pd.DataFrame(data["candles"])
    # {{time}} في TradingView أحيانًا يرسل unix epoch وأحيانًا ISO-8601 - ندعم الاثنين
    numeric_time = pd.to_numeric(df["time"], errors="coerce")
    parsed = pd.to_datetime(numeric_time, unit="s", errors="coerce")
    if parsed.isna().all():
        parsed = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df["time"] = parsed
    df = df.dropna(subset=["time"]).set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def fetch_multi_timeframe(store: StateStore, symbol: str, timeframes: list) -> dict:
    result = {}
    for tf in timeframes:
        try:
            result[tf] = fetch_ohlc(store, symbol, tf)
        except RuntimeError as e:
            logger.warning("tradingview_timeframe_unavailable", extra={"symbol": symbol, "timeframe": tf, "error": str(e)})
    return result
