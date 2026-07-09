"""
analysis/multi_timeframe.py
============================
يجمع تحليل الهيكل والاتجاه عبر عدة فريمات زمنية، ويحسب "درجة توافق" (alignment score)
بين الفريمات - كل ما زاد التوافق بين الفريمات الكبيرة والصغيرة، زادت قوة الإشارة.
"""
from smc.market_structure import current_trend


def analyze_multi_timeframe(data_by_tf: dict, lookback: int = 3) -> dict:
    """
    data_by_tf: dict مثل {"M15": df, "H1": df, "H4": df, "D1": df}
    يرجع: dict فيه اتجاه كل فريم + درجة توافق عامة (0-100)
    """
    trends = {}
    for tf, df in data_by_tf.items():
        if df is None or len(df) < (lookback * 2 + 5):
            trends[tf] = "بيانات غير كافية"
            continue
        trends[tf] = current_trend(df, lookback)

    up_votes = sum(1 for t in trends.values() if "صاعد" in t)
    down_votes = sum(1 for t in trends.values() if "هابط" in t)
    total_votes = up_votes + down_votes

    if total_votes == 0:
        bias, alignment_score = "غير محدد", 0
    else:
        if up_votes > down_votes:
            bias = "صاعد"
            alignment_score = round(100 * up_votes / total_votes)
        elif down_votes > up_votes:
            bias = "هابط"
            alignment_score = round(100 * down_votes / total_votes)
        else:
            bias, alignment_score = "متذبذب / بدون تحيز واضح", 50

    return {
        "trend_by_timeframe": trends,
        "overall_bias": bias,
        "alignment_score": alignment_score,
    }
