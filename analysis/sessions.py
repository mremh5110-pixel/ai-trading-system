"""
analysis/sessions.py
=====================
- تحديد الجلسة الحالية (آسيا / لندن / نيويورك) حسب UTC.
- فلتر أخبار اقتصادية: هذا الجزء يحتاج ربط فعلي بمصدر تقويم اقتصادي خارجي
  (مثل ForexFactory / Finnhub / TradingEconomics API) لأنه ليس لدينا وصول شبكي
  لهذه الخدمات من هذه البيئة. الكود هنا جاهز كواجهة (interface) تربطها بأي مزود
  تختاره بأقل تعديل ممكن.
"""
from datetime import datetime, timezone
import requests


def get_active_sessions(now: datetime = None, sessions_cfg: dict = None) -> list:
    now = now or datetime.now(timezone.utc)
    hour = now.hour
    active = []
    for name, (start, end) in sessions_cfg.items():
        if start <= hour < end:
            active.append(name)
    return active


class NewsFilter:
    """
    واجهة عامة لفلتر الأخبار. مرّر أي دالة fetch_fn ترجع قائمة أخبار بالشكل:
    [{"time": datetime, "impact": "high"/"medium"/"low", "currency": "USD", "title": "..."}]
    مثال على مزوّد حقيقي: Finnhub Economic Calendar API (يتطلب API key).
    """

    def __init__(self, fetch_fn=None, blackout_minutes_before=30, blackout_minutes_after=30):
        self.fetch_fn = fetch_fn
        self.before = blackout_minutes_before
        self.after = blackout_minutes_after

    def is_high_impact_news_nearby(self, now: datetime, currencies: list) -> dict:
        if self.fetch_fn is None:
            return {"blocked": False, "reason": "لا يوجد مزود أخبار مُفعّل - أضف fetch_fn في NewsFilter"}
        try:
            events = self.fetch_fn()
        except Exception as e:
            return {"blocked": False, "reason": f"فشل جلب الأخبار: {e}"}

        for ev in events:
            if ev.get("impact") != "high":
                continue
            if ev.get("currency") not in currencies:
                continue
            delta_min = abs((ev["time"] - now).total_seconds()) / 60
            if delta_min <= max(self.before, self.after):
                return {
                    "blocked": True,
                    "reason": f"خبر عالي التأثير قريب: {ev.get('title', 'غير معروف')} ({ev['time']})",
                }
        return {"blocked": False, "reason": "لا يوجد خبر عالي التأثير قريب"}


def example_finnhub_fetch_fn(api_key: str):
    """مثال جاهز للاستخدام مع Finnhub - عدّل حسب المزود اللي تختاره."""
    def _fetch():
        url = f"https://finnhub.io/api/v1/calendar/economic?token={api_key}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("economicCalendar", [])
        out = []
        for r in raw:
            out.append({
                "time": datetime.fromisoformat(r["time"]),
                "impact": r.get("impact", "low"),
                "currency": r.get("country", ""),
                "title": r.get("event", ""),
            })
        return out
    return _fetch
