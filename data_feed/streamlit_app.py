"""
streamlit_app.py
==================
نسخة "موقع ويب فقط" من النظام - ملف واحد ذاتي الاكتفاء، مصمَّم خصيصًا
للاستضافة المجانية على Streamlit Community Cloud (https://share.streamlit.io).

يدعم مصدرين للبيانات:
- تجريبي (Demo): بيانات صناعية، يعمل دايمًا 100% بدون أي اعتماد خارجي.
- حقيقي (Yahoo Finance): بيانات سوق فعلية مجانية بدون تسجيل - راجع
  data_feed/yahoo_feed.py للتفاصيل والتنويهات المهمة عن هذا المصدر.

لو فشل جلب البيانات الحقيقية لأي سبب (رفض مؤقت من Yahoo، مشكلة شبكة، إلخ)،
النظام يرجع تلقائيًا وبأمان لبيانات Demo لنفس الرمز بدل ما يتحطم، ويوضّح
ده للمستخدم برسالة واضحة.
"""
import time
from datetime import datetime, timezone
import streamlit as st

import config
from data_feed import mt5_connector as demo_feed
from data_feed import yahoo_feed
from analysis.correlation import analyze_correlations
from ml.self_learning import SelfLearningEngine
from engine.signal_engine import generate_trade_report
from storage.state_store import get_store

st.set_page_config(page_title="لوحة التحليل الذكي للأسواق المالية", layout="wide", page_icon="📊")
st.markdown("<style>.main{direction:rtl;text-align:right}</style>", unsafe_allow_html=True)
st.title("📊 لوحة التحليل الذكي للأسواق المالية")

store = get_store()
sl_engine = SelfLearningEngine(
    store=store,
    min_trades_before_training=config.MIN_TRADES_BEFORE_TRAINING,
    retrain_every=config.RETRAIN_EVERY_N_TRADES,
)

data_source = st.sidebar.radio(
    "مصدر البيانات",
    ["حقيقي (Yahoo Finance)", "تجريبي (Demo)"],
    index=0,
)
st.caption(
    "🟢 بيانات سوق حقيقية من Yahoo Finance (قد تتأخر بضع دقائق، وترجع تلقائيًا لوضع تجريبي عند أي فشل اتصال)"
    if data_source.startswith("حقيقي")
    else "🧪 نسخة تجريبية (بيانات صناعية) - تعمل دايمًا بدون اعتماد على الإنترنت"
)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_real_data(symbol: str, _cache_buster: int):
    """يرجع (data_by_tf, used_fallback: bool, error_message: str|None)"""
    data_by_tf, errors = yahoo_feed.fetch_multi_timeframe(symbol, config.TIMEFRAMES, config.BARS_TO_FETCH)
    # لو أهم فريم (الأساسي) مش موجود، اعتبرها فشل كامل وارجع للـ demo
    if config.PRIMARY_TIMEFRAME not in data_by_tf or len(data_by_tf) < 2:
        primary_error = errors.get(config.PRIMARY_TIMEFRAME) or next(iter(errors.values()), "سبب غير معروف")
        return None, True, primary_error
    return data_by_tf, False, None


@st.cache_data(ttl=30, show_spinner=False)
def fetch_demo_data(symbol: str, _cache_buster: int):
    now_anchor = datetime.now(timezone.utc).replace(tzinfo=None)
    return demo_feed.generate_demo_multi_timeframe(
        config.TIMEFRAMES, config.BARS_TO_FETCH, seed_offset=hash(symbol) % 1000, end=now_anchor
    )


def run_analysis(symbol: str, use_real: bool, cache_buster: int):
    fallback_used = False
    fallback_reason = None

    if use_real:
        data_by_tf, fallback_used, fallback_reason = fetch_real_data(symbol, cache_buster)
        if data_by_tf is None:
            data_by_tf = fetch_demo_data(symbol, cache_buster)
    else:
        data_by_tf = fetch_demo_data(symbol, cache_buster)

    correlations = None
    if use_real and not fallback_used:
        related = config.CORRELATION_SYMBOLS.get(symbol)
        if related:
            try:
                related_data = {}
                for rel_sym in related:
                    df = yahoo_feed.fetch_ohlc(rel_sym, config.PRIMARY_TIMEFRAME, config.BARS_TO_FETCH)
                    related_data[rel_sym] = df["close"]
                base_close = data_by_tf[config.PRIMARY_TIMEFRAME]["close"]
                correlations = analyze_correlations(symbol, base_close, related_data)
            except Exception:
                correlations = None  # الارتباطات ثانوية - تجاهل فشلها بدل تعطيل التقرير كله

    report = generate_trade_report(
        symbol=symbol, data_by_tf=data_by_tf,
        self_learning_engine=sl_engine, news_filter=None, correlations=correlations,
    )
    result = report.to_dict()
    result["_fallback_used"] = fallback_used
    result["_fallback_reason"] = fallback_reason
    return result


auto_refresh = st.sidebar.checkbox("تحديث تلقائي كل 60 ثانية", value=False)
if st.sidebar.button("🔄 تحديث الآن"):
    st.cache_data.clear()

use_real = data_source.startswith("حقيقي")
cache_buster = int(time.time() // (60 if use_real else 30))

for symbol in config.SYMBOLS:
    r = run_analysis(symbol, use_real, cache_buster)
    with st.container(border=True):
        if r.get("_fallback_used"):
            st.warning(f"⚠️ {symbol}: {r['_fallback_reason']} - جاري عرض بيانات تجريبية مؤقتًا بدلًا منها")

        cols = st.columns([2, 2, 2, 2, 2])
        direction_ar = "🟢 شراء" if r["direction"] == "buy" else ("🔴 بيع" if r["direction"] == "sell" else "⚪ لا يوجد")
        cols[0].metric("الرمز", symbol)
        cols[1].metric("القرار", direction_ar)
        cols[2].metric("درجة التوافق", f"{r['confluence_score']}/100")
        cols[3].metric("الجودة", r["quality"])
        ml_p = r.get("ml_win_probability")
        cols[4].metric("احتمال النجاح (AI)", f"{ml_p*100:.1f}%" if ml_p is not None else "غير متاح بعد")

        if r["direction"]:
            lvl_cols = st.columns(len(r["targets"]) + 2)
            lvl_cols[0].write(f"**الدخول:** {r['entry']}")
            lvl_cols[1].write(f"**وقف الخسارة:** {r['stop_loss']}")
            for i, (tp, val) in enumerate(r["targets"].items(), start=2):
                lvl_cols[i].write(f"**{tp}:** {val}")

            st.progress(min(r["confluence_score"], 100) / 100,
                        text=f"جاهزية الصفقة: {'✅ يُنصح بالدخول' if r['tradable'] else '⏳ يُفضّل الانتظار'}")

            with st.expander("أسباب الدخول والتحذيرات"):
                st.write("**أسباب الدخول:**")
                for reason in r["reasons_for"]:
                    st.write(f"- {reason}")
                if r["reasons_against"]:
                    st.write("**تحذيرات:**")
                    for reason in r["reasons_against"]:
                        st.write(f"- {reason}")

            with st.expander("الاتجاه حسب كل فريم زمني"):
                st.json(r["mtf_summary"]["trend_by_timeframe"])
        else:
            st.info("لا توجد صفقة مقترحة حاليًا: " + "؛ ".join(r["reasons_against"]))

st.divider()
st.caption(
    "⚠️ تنويه: النظام أداة تحليل ومساعدة على القرار وليس نصيحة مالية أو ضمانًا للربح. "
    "بيانات Yahoo Finance مصدر عام غير رسمي وقد تتأخر - لا تُستخدم كأساس وحيد لقرارات مالية حقيقية."
)

if auto_refresh:
    time.sleep(60 if use_real else 30)
    st.rerun()
