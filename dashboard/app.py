"""
dashboard/app.py (production version)
=======================================
يقرأ من StateStore (محلي أو Firestore) بدل ملف JSON محلي - هذا يسمح بتشغيل
اللوحة كخدمة Cloud Run منفصلة تمامًا عن محرك التحليل (اللي ممكن يكون شغّال
على Compute Engine)، وكلاهما يشوف نفس البيانات لحظيًا عبر Firestore.

التشغيل محليًا:
    streamlit run dashboard/app.py

التشغيل كـ Cloud Run (بعد ضبط STORE_BACKEND=firestore و GOOGLE_CLOUD_PROJECT):
    نفس الأمر، لكن داخل الحاوية - راجع deploy/gcp/
"""
import time
import streamlit as st

from storage.state_store import get_store

st.set_page_config(page_title="لوحة تحليل السوق الذكية", layout="wide", page_icon="📊")
st.markdown("<style>.main{direction:rtl;text-align:right}</style>", unsafe_allow_html=True)
st.title("📊 لوحة التحليل الذكي للأسواق المالية")

store = get_store()

auto_refresh = st.sidebar.checkbox("تحديث تلقائي كل 10 ثواني", value=True)
symbol_filter = st.sidebar.text_input("فلترة برمز معيّن (اختياري)", "")


def render():
    reports = store.get_all_signals()
    if not reports:
        st.warning("لا توجد بيانات بعد. شغّل main.py أولًا لإنتاج التقارير (محليًا أو على GCP).")
        return

    if symbol_filter:
        reports = {k: v for k, v in reports.items() if symbol_filter.upper() in k.upper()}

    for symbol, r in reports.items():
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

    st.caption(f"آخر تحديث معروض: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    st.divider()
    st.caption(
        "⚠️ تنويه: هذا النظام أداة تحليل ومساعدة على القرار وليس نصيحة مالية أو ضمانًا "
        "للربح. اختبر أي إشارة على حساب تجريبي أولًا، وطبّق إدارة مخاطر صارمة."
    )


render()

if auto_refresh:
    time.sleep(10)
    st.rerun()
