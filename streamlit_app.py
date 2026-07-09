"""
streamlit_app.py
==================
نسخة "موقع ويب فقط" من النظام - ملف واحد ذاتي الاكتفاء، مصمَّم خصيصًا
للاستضافة المجانية على Streamlit Community Cloud (https://share.streamlit.io).

الفرق عن dashboard/app.py الأصلي: مفيش محرك تحليل منفصل (main.py) لازم يفضل
شغّال في الخلفية - كل التحليل يحصل داخل نفس التطبيق مباشرة عند فتح الصفحة،
باستخدام بيانات تجريبية (demo) واقعية الشكل. هذا يخلي النظام "موقع" حقيقي
تقدر تفتحه من أي متصفح بدون تشغيل أي حاجة على جهازك.

⚠️ بيانات تجريبية فقط في هذه النسخة (مش MT5/TradingView حقيقي) - الهدف
منها إنك تشوف الواجهة والتحليل شغّالين كموقع فعلي أولًا. لربط بيانات حقيقية
لاحقًا، راجع README.md (يحتاج خطوة استضافة إضافية موضّحة هناك).
"""
import time
import streamlit as st

import config
from data_feed import mt5_connector as feed
from analysis.correlation import analyze_correlations
from ml.self_learning import SelfLearningEngine
from engine.signal_engine import generate_trade_report
from storage.state_store import get_store

st.set_page_config(page_title="لوحة التحليل الذكي للأسواق المالية", layout="wide", page_icon="📊")
st.markdown("<style>.main{direction:rtl;text-align:right}</style>", unsafe_allow_html=True)
st.title("📊 لوحة التحليل الذكي للأسواق المالية")
st.caption("نسخة تجريبية (بيانات صناعية) - تعمل بالكامل كموقع ويب مستقل")

store = get_store()
sl_engine = SelfLearningEngine(
    store=store,
    min_trades_before_training=config.MIN_TRADES_BEFORE_TRAINING,
    retrain_every=config.RETRAIN_EVERY_N_TRADES,
)


@st.cache_data(ttl=30, show_spinner=False)
def run_analysis(symbol: str, _cache_buster: int):
    """_cache_buster يتغيّر كل 30 ثانية عشان نجبر إعادة الحساب - نفس فكرة تحديث حي."""
    from datetime import datetime, timezone
    now_anchor = datetime.now(timezone.utc).replace(tzinfo=None)
    data_by_tf = feed.generate_demo_multi_timeframe(
        config.TIMEFRAMES, config.BARS_TO_FETCH, seed_offset=hash(symbol) % 1000, end=now_anchor
    )

    correlations = None
    related = config.CORRELATION_SYMBOLS.get(symbol)
    if related:
        related_data = {}
        for rel_sym in related:
            related_data[rel_sym] = feed.generate_demo_ohlc(
                config.BARS_TO_FETCH, seed=hash(rel_sym) % 1000, end=now_anchor
            )["close"]
        base_close = data_by_tf[config.PRIMARY_TIMEFRAME]["close"]
        correlations = analyze_correlations(symbol, base_close, related_data)

    report = generate_trade_report(
        symbol=symbol, data_by_tf=data_by_tf,
        self_learning_engine=sl_engine, news_filter=None, correlations=correlations,
    )
    return report.to_dict()


auto_refresh = st.sidebar.checkbox("تحديث تلقائي كل 30 ثانية", value=False)
if st.sidebar.button("🔄 تحديث الآن"):
    st.cache_data.clear()

cache_buster = int(time.time() // 30)  # يتغيّر كل 30 ثانية فيجبر إعادة الحساب

for symbol in config.SYMBOLS:
    r = run_analysis(symbol, cache_buster)
    with st.container(border=True):
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
    "⚠️ تنويه: هذه نسخة تجريبية ببيانات صناعية وليست بيانات سوق حقيقية. "
    "النظام أداة تحليل مساعدة وليس نصيحة مالية أو ضمانًا للربح."
)

if auto_refresh:
    time.sleep(30)
    st.rerun()
