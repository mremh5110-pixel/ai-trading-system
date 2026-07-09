"""
engine/signal_engine.py
========================
المحرك المركزي: يستقبل نتائج كل الوحدات (مؤشرات، هيكل سوق، سيولة، فجوات، MTF،
جلسات، ارتباطات، تعلم ذاتي) ويصهرها في قرار تداول واحد متكامل بنفس الشكل
اللي طلبته: نوع الصفقة، نسبة النجاح، درجة القوة، الأسباب، نقاط الدخول/الوقف/الأهداف،
Risk/Reward، تقييم الجودة... إلخ.

فلسفة الدرجات (Scoring):
كل عامل تحليلي (هيكل، سيولة، فجوة سعرية، مؤشر، جلسة، ارتباط) يُعطي نقاط ضمن
"درجة توافق" (confluence_score) من 0 إلى 100. هذه الدرجة قاعدية (rule-based)
ومفهومة تمامًا (شفافة) - وعندما يتوفر نموذج تعلم آلي مدرَّب (self_learning.py)
تُدمج نسبة نجاح النموذج مع الدرجة القاعدية.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import numpy as np
import pandas as pd

import config
from indicators.technical import compute_all_indicators
from smc.market_structure import (
    find_swing_points, detect_structure_breaks, current_trend,
    detect_order_blocks, detect_breaker_and_mitigation_blocks,
    detect_fvg, detect_equal_highs_lows,
)
from smc.liquidity import detect_liquidity_sweeps
from analysis.multi_timeframe import analyze_multi_timeframe
from analysis.sessions import get_active_sessions


def _score_from_bool(cond: bool, points: int) -> int:
    return points if cond else 0


def build_confluence_score(context: dict) -> dict:
    """
    يبني درجة التوافق من 100 نقطة موزعة على عوامل SMC + مؤشرات + MTF + جلسة.
    توزيع النقاط (قابل للتعديل في config.py مستقبلًا):
      - توافق الفريمات المتعددة        : 25
      - هيكل السوق (BOS/CHoCH/MSS)     : 20
      - وجود Order Block داعم           : 15
      - وجود FVG غير مُختبر داعم        : 10
      - Liquidity Sweep حديث            : 15
      - مؤشرات كلاسيكية (RSI/MACD/ADX)  : 10
      - جلسة تداول نشطة عالية السيولة   : 5
    """
    reasons_for = []
    reasons_against = []
    score = 0

    mtf = context["mtf"]
    alignment = mtf["alignment_score"]
    score += round(25 * alignment / 100)
    if alignment >= 70:
        reasons_for.append(f"توافق قوي بين الفريمات الزمنية ({alignment}%) - الاتجاه العام: {mtf['overall_bias']}")
    elif alignment >= 40:
        reasons_for.append(f"توافق متوسط بين الفريمات ({alignment}%)")
    else:
        reasons_against.append(f"تضارب بين الفريمات الزمنية (توافق {alignment}% فقط) - إشارة غير موثوقة حاليًا")

    last_events = context["structure_events"][-3:]
    has_recent_bos_or_mss = any(e["event"] in ("BOS", "MSS") for e in last_events)
    if has_recent_bos_or_mss:
        score += 20
        reasons_for.append("تأكيد هيكل سوق حديث (BOS/MSS) في اتجاه الصفقة")
    elif any(e["event"] == "CHoCH" for e in last_events):
        score += 10
        reasons_for.append("تغيّر هيكل حديث (CHoCH) - انعكاس محتمل لكن غير مؤكد بعد بـ MSS")
    else:
        reasons_against.append("لا يوجد تأكيد هيكل سوق حديث وواضح")

    if context["nearest_order_block"] is not None:
        score += 15
        ob = context["nearest_order_block"]
        reasons_for.append(f"السعر قريب من Order Block ({ob['type']}) بين {ob['low']:.5f} و {ob['high']:.5f}")
    else:
        reasons_against.append("لا يوجد Order Block قريب وداعم للسعر الحالي")

    if context["nearest_fvg"] is not None:
        score += 10
        fvg = context["nearest_fvg"]
        reasons_for.append(f"فجوة سعرية (FVG) غير مُختبرة قريبة ({fvg['type']}) بين {fvg['bottom']:.5f} و {fvg['top']:.5f}")

    if context["recent_liquidity_sweep"] is not None:
        score += 15
        sw = context["recent_liquidity_sweep"]
        reasons_for.append(sw["detail"])
    else:
        reasons_against.append("لا يوجد Liquidity Sweep حديث يدعم نقطة الدخول")

    rsi_val = context["last_row"]["rsi"]
    adx_val = context["last_row"]["adx"]
    macd_hist = context["last_row"]["hist"]
    indicator_points = 0
    if context["direction"] == "buy":
        if rsi_val < 45:
            indicator_points += 4
            reasons_for.append(f"RSI عند {rsi_val:.1f} يدعم منطقة شراء (ليس في تشبع شرائي)")
        if macd_hist > 0:
            indicator_points += 3
            reasons_for.append("MACD histogram إيجابي - زخم صاعد")
        if adx_val > 20:
            indicator_points += 3
            reasons_for.append(f"ADX عند {adx_val:.1f} يشير لترند فعّال (ليس سوقًا عرضيًا)")
    else:
        if rsi_val > 55:
            indicator_points += 4
            reasons_for.append(f"RSI عند {rsi_val:.1f} يدعم منطقة بيع (ليس في تشبع بيعي)")
        if macd_hist < 0:
            indicator_points += 3
            reasons_for.append("MACD histogram سلبي - زخم هابط")
        if adx_val > 20:
            indicator_points += 3
            reasons_for.append(f"ADX عند {adx_val:.1f} يشير لترند فعّال")
    score += indicator_points

    active_sessions = context["active_sessions"]
    if "London" in active_sessions or "New York" in active_sessions:
        score += 5
        reasons_for.append(f"الجلسة الحالية نشطة وعالية السيولة: {', '.join(active_sessions)}")
    else:
        reasons_against.append("الجلسة الحالية (آسيا فقط) عادة أقل سيولة وتقلبًا")

    score = max(0, min(100, score))
    return {"score": score, "reasons_for": reasons_for, "reasons_against": reasons_against}


def quality_label(score: int) -> str:
    if score >= 85:
        return "قوية جدًا"
    if score >= 70:
        return "قوية"
    if score >= 55:
        return "متوسطة"
    return "ضعيفة"


def build_trade_levels(context: dict, direction: str) -> dict:
    """يحدد الدخول/الوقف/الأهداف بناءً على أقرب order block / سيولة / ATR."""
    price = context["current_price"]
    atr_val = context["last_row"]["atr"]

    ob = context["nearest_order_block"]
    if ob is not None:
        if direction == "buy":
            entry = ob["high"]
            stop_loss = ob["low"] - 0.25 * atr_val
        else:
            entry = ob["low"]
            stop_loss = ob["high"] + 0.25 * atr_val
    else:
        entry = price
        stop_loss = price - 1.5 * atr_val if direction == "buy" else price + 1.5 * atr_val

    risk = abs(entry - stop_loss)
    targets = {}
    for i, rr in enumerate(config.DEFAULT_RISK_REWARD_TARGETS, start=1):
        targets[f"TP{i}"] = entry + rr * risk if direction == "buy" else entry - rr * risk

    extra_target = None
    return {
        "entry": round(float(entry), 5),
        "stop_loss": round(float(stop_loss), 5),
        "targets": {k: round(float(v), 5) for k, v in targets.items()},
        "risk_per_unit": round(float(risk), 5),
    }


@dataclass
class TradeReport:
    symbol: str
    direction: Optional[str]
    tradable: bool
    confluence_score: int
    quality: str
    reasons_for: list
    reasons_against: list
    entry: Optional[float]
    stop_loss: Optional[float]
    targets: dict
    risk_reward: Optional[float]
    ml_win_probability: Optional[float]
    ml_source: str
    mtf_summary: dict
    active_sessions: list
    generated_at: str

    def to_dict(self):
        return self.__dict__


def generate_trade_report(symbol: str, data_by_tf: dict, self_learning_engine=None,
                           news_filter=None, correlations: list = None) -> TradeReport:
    """
    data_by_tf: {"M5": df, "M15": df, "H1": df, "H4": df, "D1": df}
    كل df لازم يحتوي: open, high, low, close, (volume اختياري), index = datetime
    """
    primary_tf = config.PRIMARY_TIMEFRAME
    df = data_by_tf[primary_tf].copy()
    df = compute_all_indicators(df, config)

    swing_highs, swing_lows = find_swing_points(df, config.SWING_LOOKBACK)
    structure_events = detect_structure_breaks(df, config.SWING_LOOKBACK)
    order_blocks = detect_order_blocks(df, structure_events, atr_series=df["atr"])
    breakers, mitigations = detect_breaker_and_mitigation_blocks(df, order_blocks)
    fvgs = detect_fvg(df, atr_series=df["atr"], min_gap_atr_ratio=config.FVG_MIN_GAP_ATR_RATIO)
    eq_highs, eq_lows = detect_equal_highs_lows(swing_highs, swing_lows, config.EQUAL_LEVEL_TOLERANCE)
    sweeps = detect_liquidity_sweeps(df, swing_highs, swing_lows)

    mtf = analyze_multi_timeframe(data_by_tf, config.SWING_LOOKBACK)
    active_sessions = get_active_sessions(sessions_cfg=config.SESSIONS_UTC)

    current_price = float(df["close"].iloc[-1])
    last_row = df.iloc[-1]

    direction = "buy" if "صاعد" in mtf["overall_bias"] else ("sell" if "هابط" in mtf["overall_bias"] else None)

    nearest_ob = None
    if order_blocks:
        relevant = [b for b in order_blocks if (b["type"] == "bullish_ob") == (direction == "buy")]
        pool = relevant or order_blocks
        nearest_ob = min(pool, key=lambda b: abs(current_price - (b["high"] + b["low"]) / 2))

    nearest_fvg = None
    open_fvgs = [g for g in fvgs if not g["inversed"]]
    if open_fvgs:
        nearest_fvg = min(open_fvgs, key=lambda g: abs(current_price - (g["top"] + g["bottom"]) / 2))

    recent_sweep = sweeps[-1] if sweeps else None

    context = {
        "mtf": mtf, "structure_events": structure_events,
        "nearest_order_block": nearest_ob, "nearest_fvg": nearest_fvg,
        "recent_liquidity_sweep": recent_sweep, "last_row": last_row,
        "direction": direction or "buy", "active_sessions": active_sessions,
        "current_price": current_price,
    }

    if direction is None:
        return TradeReport(
            symbol=symbol, direction=None, tradable=False, confluence_score=0,
            quality="لا توجد صفقة", reasons_for=[],
            reasons_against=["لا يوجد اتجاه واضح متوافق عليه بين الفريمات الزمنية حاليًا"],
            entry=None, stop_loss=None, targets={}, risk_reward=None,
            ml_win_probability=None, ml_source="none", mtf_summary=mtf,
            active_sessions=active_sessions, generated_at=datetime.now(timezone.utc).isoformat(),
        )

    conf = build_confluence_score(context)
    levels = build_trade_levels(context, direction)

    if conf["score"] >= config.MIN_CONFLUENCE_SCORE_TO_TRADE and conf["score"] >= 85:
        extra_rr = config.STRONG_SETUP_EXTRA_TARGET_RR
        risk = levels["risk_per_unit"]
        entry = levels["entry"]
        tp4 = entry + extra_rr * risk if direction == "buy" else entry - extra_rr * risk
        levels["targets"]["TP4"] = round(float(tp4), 5)

    ml_result = {"probability": None, "source": "rule_based_only", "note": "لا يوجد محرك تعلم ذاتي مفعّل"}
    if self_learning_engine is not None:
        features = {
            "alignment_score": mtf["alignment_score"],
            "rsi": float(last_row["rsi"]), "adx": float(last_row["adx"]),
            "atr_ratio_to_price": float(last_row["atr"] / current_price),
            "confluence_score": conf["score"], "num_confluences": len(conf["reasons_for"]),
            "session_score": 1 if ("London" in active_sessions or "New York" in active_sessions) else 0,
            "has_liquidity_sweep": 1 if recent_sweep else 0,
            "has_fvg": 1 if nearest_fvg else 0,
            "has_order_block": 1 if nearest_ob else 0,
            "risk_reward": config.DEFAULT_RISK_REWARD_TARGETS[0],
        }
        ml_result = self_learning_engine.predict_win_probability(features)

    if news_filter is not None:
        news_check = news_filter.is_high_impact_news_nearby(datetime.now(timezone.utc), currencies=["USD"])
        if news_check["blocked"]:
            conf["reasons_against"].append(news_check["reason"])
            conf["score"] = max(0, conf["score"] - 20)

    if correlations:
        for c in correlations:
            conf["reasons_for" if (c["correlation"] or 0) < -0.5 else "reasons_against"].append(c["interpretation"])

    tradable = conf["score"] >= config.MIN_CONFLUENCE_SCORE_TO_TRADE

    rr_first_target = config.DEFAULT_RISK_REWARD_TARGETS[0]

    return TradeReport(
        symbol=symbol,
        direction=direction,
        tradable=tradable,
        confluence_score=conf["score"],
        quality=quality_label(conf["score"]),
        reasons_for=conf["reasons_for"],
        reasons_against=conf["reasons_against"] if not tradable else conf["reasons_against"],
        entry=levels["entry"],
        stop_loss=levels["stop_loss"],
        targets=levels["targets"],
        risk_reward=rr_first_target,
        ml_win_probability=ml_result["probability"],
        ml_source=ml_result["source"],
        mtf_summary=mtf,
        active_sessions=active_sessions,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
