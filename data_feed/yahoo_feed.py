"""
data_feed/yahoo_feed.py
=========================
بيانات سوق حقيقية من Yahoo Finance - بدون تسجيل، بدون مفتاح API، تعمل مباشرة
من أي بيئة عندها اتصال إنترنت (بما فيها Streamlit Community Cloud).

⚠️ ملاحظات صادقة مهمة:
- ده مصدر بيانات عام غير رسمي (unofficial public endpoint) - مش API مدعوم
  رسميًا من Yahoo للاستخدام البرمجي، وممكن يتغيّر أو يتوقف أو يرفض طلبات من
  سيرفرات سحابية معينة أحيانًا. لو حصل، النظام يرجع تلقائيًا لوضع Demo.
- البيانات ممكن تكون متأخرة بضع دقائق (مش تيك بتيك لحظي زي بيانات بروكر حقيقي).
- لتداول حقيقي فعلي، هذا المصدر لأغراض التجربة والتعلّم فقط - مش بديل عن
  بيانات بروكر رسمية (MT5) وقت اتخاذ قرارات مالية حقيقية.
"""
from datetime import datetime
import requests
import pandas as pd

from logging_setup.logger import get_logger

logger = get_logger(__name__)

# تحويل رموزنا لرموز Yahoo Finance المعروفة
YAHOO_SYMBOL_MAP = {
    "XAUUSD": "XAUUSD=X",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
}

# Yahoo ما عندهوش فريم 4 ساعات مباشرة - بنجيبه من بيانات الساعة ونعمله resample
YAHOO_INTERVAL_MAP = {"M5": "5m", "M15": "15m", "H1": "60m", "H4": "60m", "D1": "1d"}
YAHOO_RANGE_MAP = {"M5": "5d", "M15": "1mo", "H1": "3mo", "H4": "1y", "D1": "5y"}

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch_ohlc(symbol: str, timeframe: str, bars: int = 500) -> pd.DataFrame:
    yf_symbol = YAHOO_SYMBOL_MAP.get(symbol, symbol)
    interval = YAHOO_INTERVAL_MAP.get(timeframe, "15m")
    range_ = YAHOO_RANGE_MAP.get(timeframe, "1mo")

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}"
    params = {"interval": interval, "range": range_}

    resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo Finance رجّع خطأ للرمز {yf_symbol}: {chart['error']}")
    results = chart.get("result")
    if not results:
        raise RuntimeError(f"لا توجد بيانات من Yahoo Finance للرمز {yf_symbol}")

    result = results[0]
    timestamps = result.get("timestamp")
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    if not timestamps or not quote.get("close"):
        raise RuntimeError(f"بيانات فارغة من Yahoo Finance للرمز {yf_symbol}")

    df = pd.DataFrame({
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close"),
        "volume": quote.get("volume") or [0] * len(timestamps),
    }, index=pd.to_datetime(timestamps, unit="s", utc=True))

    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise RuntimeError(f"كل صفوف البيانات فارغة بعد التنظيف للرمز {yf_symbol}")

    if timeframe == "H4":
        df = df.resample("4h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()

    return df.tail(bars)


def fetch_multi_timeframe(symbol: str, timeframes: list, bars: int = 500) -> dict:
    result = {}
    for tf in timeframes:
        try:
            result[tf] = fetch_ohlc(symbol, tf, bars)
        except Exception as e:
            logger.warning("yahoo_timeframe_fetch_failed", extra={"symbol": symbol, "timeframe": tf, "error": str(e)})
    return result
