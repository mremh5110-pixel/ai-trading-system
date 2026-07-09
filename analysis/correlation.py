"""
analysis/correlation.py
========================
تحليل العلاقة بين رمز أساسي (مثل XAUUSD) ورموز مرتبطة (DXY، عوائد السندات، إلخ).
يحسب معامل الارتباط المتحرك (rolling correlation) ويصدر قراءة نصية.
"""
import pandas as pd


def rolling_correlation(base_close: pd.Series, related_close: pd.Series, window: int = 50) -> pd.Series:
    aligned = pd.DataFrame({"base": base_close, "related": related_close}).dropna()
    return aligned["base"].rolling(window).corr(aligned["related"])


def interpret_correlation(base_symbol: str, related_symbol: str, corr_value: float) -> str:
    if pd.isna(corr_value):
        return f"بيانات غير كافية لحساب الارتباط بين {base_symbol} و {related_symbol}"
    if corr_value <= -0.6:
        return f"ارتباط عكسي قوي بين {base_symbol} و {related_symbol} ({corr_value:.2f}) - تحرك {related_symbol} يدعم التحليل"
    if corr_value >= 0.6:
        return f"ارتباط طردي قوي بين {base_symbol} و {related_symbol} ({corr_value:.2f})"
    return f"ارتباط ضعيف/غير واضح حاليًا بين {base_symbol} و {related_symbol} ({corr_value:.2f}) - لا يُعتمد عليه كعامل قرار الآن"


def analyze_correlations(base_symbol: str, base_close: pd.Series, related_data: dict, window: int = 50) -> list:
    """
    related_data: dict مثل {"DXY": close_series, "US10Y": close_series}
    """
    results = []
    for sym, series in related_data.items():
        corr_series = rolling_correlation(base_close, series, window)
        latest = corr_series.iloc[-1] if len(corr_series) else float("nan")
        results.append({
            "symbol": sym,
            "correlation": None if pd.isna(latest) else round(float(latest), 3),
            "interpretation": interpret_correlation(base_symbol, sym, latest),
        })
    return results
