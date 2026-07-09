"""
tests/test_indicators.py
==========================
اختبارات حقيقية على منطق المؤشرات - مش mocks فاضية. نتحقق من خصائص رياضية
معروفة (RSI بين 0-100، MACD يتقاطع صح، ATR دايمًا موجب، إلخ).
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from indicators.technical import rsi, macd, atr, bollinger_bands, adx, sma, ema


def make_trending_df(n=200, direction=1, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(direction * 0.1, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = close + rng.uniform(-0.5, 0.5, n)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


def test_rsi_bounds():
    df = make_trending_df()
    r = rsi(df["close"], 14)
    assert (r >= 0).all() and (r <= 100).all()


def test_rsi_uptrend_above_50_mostly():
    df = make_trending_df(direction=1)
    r = rsi(df["close"], 14).dropna()
    assert r.mean() > 50


def test_rsi_downtrend_below_50_mostly():
    df = make_trending_df(direction=-1)
    r = rsi(df["close"], 14).dropna()
    assert r.mean() < 50


def test_macd_columns_and_hist_consistency():
    df = make_trending_df()
    m = macd(df["close"])
    assert set(["macd", "signal", "hist"]).issubset(m.columns)
    # hist لازم يساوي macd - signal بالضبط
    assert np.allclose((m["macd"] - m["signal"]).values, m["hist"].values, atol=1e-9)


def test_atr_always_non_negative():
    df = make_trending_df()
    a = atr(df, 14)
    assert (a.dropna() >= 0).all()


def test_bollinger_upper_above_lower():
    df = make_trending_df()
    bb = bollinger_bands(df["close"], 20, 2)
    valid = bb.dropna()
    assert (valid["bb_upper"] >= valid["bb_mid"]).all()
    assert (valid["bb_mid"] >= valid["bb_lower"]).all()


def test_adx_bounds():
    df = make_trending_df()
    a = adx(df, 14)
    assert (a >= 0).all() and (a <= 100).all()


def test_ema_reacts_faster_than_sma():
    # في قفزة سعرية مفاجئة، EMA لازم يتحرك أسرع من SMA بنفس الفترة
    close = pd.Series([100] * 50 + [110] * 20)
    s = sma(close, 10)
    e = ema(close, 10)
    jump_idx = 55  # بعد القفزة بـ 5 شموع
    assert e.iloc[jump_idx] > s.iloc[jump_idx]
