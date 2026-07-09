"""
smc/market_structure.py
========================
كشف هيكل السوق بمنطق Smart Money Concepts / ICT:
- Swing Highs / Swing Lows
- BOS (Break of Structure) / CHoCH (Change of Character) / MSS
- Order Blocks (Bullish / Bearish)
- Breaker Blocks
- Mitigation Blocks
- Fair Value Gaps (FVG) و Inverse FVG
- Equal Highs / Equal Lows (مناطق سيولة)

كل الدوال بترجع بيانات structured (list[dict]) عشان تتحول بسهولة لـ JSON للوحة أو للـ ML.
"""
from dataclasses import dataclass, field
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Swing points
# ---------------------------------------------------------------------------
def find_swing_points(df: pd.DataFrame, lookback: int = 3):
    """
    نقطة قمة (swing high) = أعلى high خلال [i-lookback, i+lookback]
    نقطة قاع (swing low)  = أقل low خلال نفس النطاق
    يرجع قائمتين من dict: [{index, price, type}]
    """
    highs, lows = [], []
    h, l = df["high"].values, df["low"].values
    n = len(df)
    for i in range(lookback, n - lookback):
        window_h = h[i - lookback:i + lookback + 1]
        window_l = l[i - lookback:i + lookback + 1]
        if h[i] == window_h.max() and np.argmax(window_h) == lookback:
            highs.append({"idx": i, "time": df.index[i], "price": float(h[i]), "type": "swing_high"})
        if l[i] == window_l.min() and np.argmin(window_l) == lookback:
            lows.append({"idx": i, "time": df.index[i], "price": float(l[i]), "type": "swing_low"})
    return highs, lows


# ---------------------------------------------------------------------------
# BOS / CHoCH / MSS
# ---------------------------------------------------------------------------
def detect_structure_breaks(df: pd.DataFrame, lookback: int = 3):
    """
    يبني تسلسل الـ swing points ثم يحدد:
    - BOS  : كسر قمة/قاع في اتجاه الترند الحالي (استمرارية)
    - CHoCH: كسر أول قمة/قاع مضاد للترند الحالي (إشارة انعكاس محتملة)
    - MSS  : تأكيد تغيّر الهيكل بعد CHoCH (كسر إضافي في نفس الاتجاه الجديد)
    يرجع قائمة أحداث مرتبة زمنيًا.
    """
    highs, lows = find_swing_points(df, lookback)
    points = sorted(highs + lows, key=lambda p: p["idx"])
    if len(points) < 3:
        return []

    events = []
    trend = None  # "up" / "down"
    last_high = None
    last_low = None

    for p in points:
        if p["type"] == "swing_high":
            if last_high is not None and p["price"] > last_high["price"]:
                if trend == "down":
                    events.append({**p, "event": "CHoCH", "detail": "كسر قمة سابقة أثناء ترند هابط -> انعكاس محتمل للأعلى"})
                    trend = "up"
                elif trend == "up":
                    events.append({**p, "event": "BOS", "detail": "استمرار الترند الصاعد - كسر قمة جديدة"})
                elif trend is None:
                    trend = "up"
            last_high = p
        else:  # swing_low
            if last_low is not None and p["price"] < last_low["price"]:
                if trend == "up":
                    events.append({**p, "event": "CHoCH", "detail": "كسر قاع سابق أثناء ترند صاعد -> انعكاس محتمل للأسفل"})
                    trend = "down"
                elif trend == "down":
                    events.append({**p, "event": "BOS", "detail": "استمرار الترند الهابط - كسر قاع جديد"})
                elif trend is None:
                    trend = "down"
            last_low = p

    # MSS = أول BOS بعد CHoCH يعتبر تأكيد رسمي لتغيّر الهيكل
    for i, e in enumerate(events):
        if e["event"] == "BOS" and i > 0 and events[i - 1]["event"] == "CHoCH":
            e["event"] = "MSS"
            e["detail"] = "تأكيد تغيّر الهيكل (MSS) بعد CHoCH"

    return events


def current_trend(df: pd.DataFrame, lookback: int = 3) -> str:
    events = detect_structure_breaks(df, lookback)
    if not events:
        return "غير محدد"
    last = events[-1]["event"]
    last_type = events[-1]["type"]
    if last in ("BOS", "MSS"):
        return "صاعد" if last_type == "swing_high" else "هابط"
    if last == "CHoCH":
        return "صاعد (انعكاس محتمل)" if last_type == "swing_high" else "هابط (انعكاس محتمل)"
    return "غير محدد"


# ---------------------------------------------------------------------------
# Order Blocks / Breaker Blocks / Mitigation Blocks
# ---------------------------------------------------------------------------
def detect_order_blocks(df: pd.DataFrame, structure_events, impulse_atr_mult: float = 1.5, atr_series: pd.Series = None):
    """
    Order Block صاعد: آخر شمعة هابطة قبل حركة اندفاعية صاعدة كسرت هيكلًا (BOS/CHoCH up)
    Order Block هابط: آخر شمعة صاعدة قبل حركة اندفاعية هابطة كسرت هيكلًا (BOS/CHoCH down)
    """
    if atr_series is None:
        from indicators.technical import atr as atr_fn
        atr_series = atr_fn(df, 14)

    blocks = []
    for ev in structure_events:
        idx = ev["idx"]
        direction_up = ev["type"] == "swing_high"  # كسر قمة = حركة صاعدة
        # نبحث للخلف عن آخر شمعة معاكسة الاتجاه قبل الاندفاعة
        search_start = max(0, idx - 15)
        segment = df.iloc[search_start:idx + 1]
        candle = None
        for j in range(len(segment) - 1, -1, -1):
            c = segment.iloc[j]
            is_bearish = c["close"] < c["open"]
            is_bullish = c["close"] > c["open"]
            if direction_up and is_bearish:
                candle = (segment.index[j], c)
                break
            if not direction_up and is_bullish:
                candle = (segment.index[j], c)
                break
        if candle is None:
            continue
        t, c = candle
        move_size = abs(df.loc[ev["time"], "close"] - c["close"]) if ev["time"] in df.index else 0
        a = atr_series.loc[t] if t in atr_series.index else np.nan
        is_impulsive = (not np.isnan(a)) and move_size >= impulse_atr_mult * a
        blocks.append({
            "time": t,
            "type": "bullish_ob" if direction_up else "bearish_ob",
            "high": float(c["high"]),
            "low": float(c["low"]),
            "related_event": ev["event"],
            "impulsive": bool(is_impulsive),
        })
    return blocks


def detect_breaker_and_mitigation_blocks(df: pd.DataFrame, order_blocks):
    """
    Breaker Block  : أوردر بلوك تم كسره سعريًا بعكس اتجاهه الأصلي، ثم أصبح منطقة اهتمام معاكسة.
    Mitigation Block: منطقة عودة السعر "لتخفيف" آخر أوردر بلوك مضاد قبل استكمال الاتجاه، دون كسر كامل.
    """
    breakers, mitigations = [], []
    for ob in order_blocks:
        t = ob["time"]
        future = df[df.index > t]
        if future.empty:
            continue
        if ob["type"] == "bullish_ob":
            broken = future[future["close"] < ob["low"]]
            touched_not_broken = future[(future["low"] <= ob["high"]) & (future["close"] >= ob["low"])]
        else:
            broken = future[future["close"] > ob["high"]]
            touched_not_broken = future[(future["high"] >= ob["low"]) & (future["close"] <= ob["high"])]

        if not broken.empty:
            breakers.append({**ob, "type": "breaker_" + ob["type"], "broken_at": broken.index[0]})
        elif not touched_not_broken.empty:
            mitigations.append({**ob, "type": "mitigation_" + ob["type"], "mitigated_at": touched_not_broken.index[0]})
    return breakers, mitigations


# ---------------------------------------------------------------------------
# Fair Value Gaps (FVG) + Inverse FVG
# ---------------------------------------------------------------------------
def detect_fvg(df: pd.DataFrame, atr_series: pd.Series = None, min_gap_atr_ratio: float = 0.15):
    """
    FVG صاعد: low الشمعة 3 > high الشمعة 1 (فجوة سعرية لم تُتداول)
    FVG هابط: high الشمعة 3 < low الشمعة 1
    Inverse FVG: فجوة تم اختراقها بالكامل بعكس اتجاهها الأصلي -> تتحول لمنطقة اهتمام معاكسة.
    """
    if atr_series is None:
        from indicators.technical import atr as atr_fn
        atr_series = atr_fn(df, 14)

    gaps = []
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    for i in range(2, len(df)):
        a = atr_series.iloc[i]
        if np.isnan(a) or a == 0:
            continue
        # Bullish FVG
        if l[i] > h[i - 2]:
            gap_size = l[i] - h[i - 2]
            if gap_size >= min_gap_atr_ratio * a:
                gaps.append({
                    "time": df.index[i], "type": "bullish_fvg",
                    "top": float(l[i]), "bottom": float(h[i - 2]), "size": float(gap_size),
                })
        # Bearish FVG
        if h[i] < l[i - 2]:
            gap_size = l[i - 2] - h[i]
            if gap_size >= min_gap_atr_ratio * a:
                gaps.append({
                    "time": df.index[i], "type": "bearish_fvg",
                    "top": float(l[i - 2]), "bottom": float(h[i]), "size": float(gap_size),
                })

    # تحديد أي الفجوات تحولت لـ Inverse FVG (تم اختراقها بالكامل بعكس اتجاهها)
    for g in gaps:
        future = df[df.index > g["time"]]
        if g["type"] == "bullish_fvg":
            broken = future[future["close"] < g["bottom"]]
        else:
            broken = future[future["close"] > g["top"]]
        g["inversed"] = not broken.empty
        if g["inversed"]:
            g["inversed_at"] = broken.index[0]

    return gaps


# ---------------------------------------------------------------------------
# Equal Highs / Equal Lows (مناطق سيولة محتملة)
# ---------------------------------------------------------------------------
def detect_equal_highs_lows(highs, lows, tolerance: float = 0.0006):
    def cluster(points, price_key="price"):
        clusters = []
        used = set()
        for i, p1 in enumerate(points):
            if i in used:
                continue
            group = [p1]
            for j, p2 in enumerate(points):
                if j <= i or j in used:
                    continue
                if abs(p1[price_key] - p2[price_key]) / p1[price_key] <= tolerance:
                    group.append(p2)
                    used.add(j)
            if len(group) >= 2:
                clusters.append(group)
        return clusters

    eq_highs = cluster(highs)
    eq_lows = cluster(lows)
    return eq_highs, eq_lows
