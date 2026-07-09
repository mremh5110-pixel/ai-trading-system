"""
smc/liquidity.py
=================
كشف Liquidity Sweeps: اختراق سعري لقمة/قاع سابق بالفتيل فقط (wick) ثم إغلاق السعر
داخل النطاق مرة أخرى - إشارة كلاسيكية على "صيد السيولة" من قبل المؤسسات قبل
انعكاس الاتجاه الحقيقي.
"""
import pandas as pd


def detect_liquidity_sweeps(df: pd.DataFrame, swing_highs, swing_lows, confirm_bars: int = 3):
    sweeps = []

    for sh in swing_highs:
        level = sh["price"]
        idx = sh["idx"]
        window = df.iloc[idx + 1: idx + 1 + confirm_bars]
        for t, row in window.iterrows():
            if row["high"] > level and row["close"] < level:
                sweeps.append({
                    "time": t, "type": "sell_side_sweep_of_high",
                    "level": float(level), "wick_high": float(row["high"]),
                    "detail": "اختراق سيولة فوق قمة سابقة ثم إغلاق تحتها - احتمال انعكاس هابط",
                })
                break

    for sl in swing_lows:
        level = sl["price"]
        idx = sl["idx"]
        window = df.iloc[idx + 1: idx + 1 + confirm_bars]
        for t, row in window.iterrows():
            if row["low"] < level and row["close"] > level:
                sweeps.append({
                    "time": t, "type": "buy_side_sweep_of_low",
                    "level": float(level), "wick_low": float(row["low"]),
                    "detail": "اختراق سيولة تحت قاع سابق ثم إغلاق فوقه - احتمال انعكاس صاعد",
                })
                break

    return sorted(sweeps, key=lambda s: s["time"])
