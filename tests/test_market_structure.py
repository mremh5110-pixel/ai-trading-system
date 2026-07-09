"""
tests/test_market_structure.py
================================
اختبارات على منطق SMC: هل النظام يكتشف فعلًا هيكل سوق صاعد/هابط واضح في بيانات
اصطناعية مصمَّمة خصيصًا (مش عشوائية) للتحقق من صحة الخوارزمية؟
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from smc.market_structure import (
    find_swing_points, detect_structure_breaks, current_trend, detect_fvg,
    detect_equal_highs_lows,
)


def make_zigzag(n_legs=8, leg_bars=10, leg_size=8, net_drift=3, seed=7):
    """
    يبني سلسلة أسعار متعرجة (zigzag) حقيقية: كل رجل يصعد ثم يتراجع جزئيًا،
    لكن بانحياز صافٍ (net_drift) لأعلى أو لأسفل عبر الأرجل - يضمن وجود swing
    points حقيقية (قمم وقيعان محلية) مع اتجاه عام واضح، بعكس سلسلة رتيبة
    الاتجاه بدون أي تراجع محلي (اللي معناها رياضيًا صفر swing points).
    """
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for leg in range(n_legs):
        up_bars = leg_bars // 2
        down_bars = leg_bars - up_bars
        for _ in range(up_bars):
            prices.append(prices[-1] + leg_size / up_bars + rng.uniform(-0.2, 0.2))
        for _ in range(down_bars):
            prices.append(prices[-1] - (leg_size - net_drift) / down_bars + rng.uniform(-0.2, 0.2))
    close = pd.Series(prices)
    high = (close + 0.8).values
    low = (close - 0.8).values
    close = close.values
    idx = pd.date_range("2024-01-01", periods=len(close), freq="15min")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)



def test_swing_points_detected_in_staircase():
    df = make_zigzag(net_drift=3)
    highs, lows = find_swing_points(df, lookback=3)
    assert len(highs) >= 3
    assert len(lows) >= 3


def test_uptrend_detected_as_up():
    df = make_zigzag(net_drift=3)   # كل رجل يصعد أكثر مما يتراجع -> اتجاه صاعد صافٍ
    trend = current_trend(df, lookback=3)
    assert "صاعد" in trend


def test_downtrend_detected_as_down():
    df = make_zigzag(net_drift=-3)  # كل رجل يتراجع أكثر مما يصعد -> اتجاه هابط صافٍ
    trend = current_trend(df, lookback=3)
    assert "هابط" in trend


def test_structure_events_are_chronological():
    df = make_zigzag(net_drift=3)
    events = detect_structure_breaks(df, lookback=3)
    assert len(events) >= 2   # يجب أن يكتشف أحداث حقيقية، وليس قائمة فارغة
    idxs = [e["idx"] for e in events]
    assert idxs == sorted(idxs)


def test_fvg_detection_on_synthetic_gap():
    # خلفية واقعية بتذبذب بسيط (مش قيم ثابتة) لتفادي فجوات زائفة، ثم فجوة صريحة
    # مزروعة عند شموع محددة: شمعة 1 (idx=10) قمتها 100، شمعة 3 (idx=12) قاعها 105.
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    rng = np.random.default_rng(3)
    base = 95 + rng.uniform(-0.3, 0.3, n)
    open_, high, low, close = base.copy(), base + 0.5, base - 0.5, base.copy()
    high[10], low[10], close[10], open_[10] = 100, 99, 99.5, 99.5   # الشمعة 1
    high[11], low[11], close[11], open_[11] = 103, 101, 102, 101   # شمعة اندفاعية
    high[12], low[12], close[12], open_[12] = 107, 105, 106, 105   # الشمعة 3: low=105 > high شمعة1=100
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

    from indicators.technical import atr as atr_fn
    atr_series = atr_fn(df, 14).fillna(0.5) + 0.05
    gaps = detect_fvg(df, atr_series=atr_series, min_gap_atr_ratio=0.01)

    match = [g for g in gaps if g["type"] == "bullish_fvg" and g["time"] == df.index[12]]
    assert len(match) == 1
    assert match[0]["bottom"] == 100
    assert match[0]["top"] == 105


def test_equal_highs_clustering():
    highs = [
        {"idx": 1, "price": 100.00, "type": "swing_high"},
        {"idx": 5, "price": 100.02, "type": "swing_high"},   # قريبة جدًا من الأولى
        {"idx": 9, "price": 120.00, "type": "swing_high"},   # بعيدة تمامًا
    ]
    lows = []
    eq_highs, eq_lows = detect_equal_highs_lows(highs, lows, tolerance=0.001)
    assert len(eq_highs) == 1
    assert len(eq_highs[0]) == 2
