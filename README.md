# نظام تحليل الأسواق المالية الذكي (AI Market Analysis System)

إطار عمل احترافي وقابل للتشغيل فعليًا يدمج SMC / ICT / Price Action مع مؤشرات
كلاسيكية وتعلّم ذاتي، ويصدر تقرير قرار تداول كامل (دخول، وقف، أهداف، نسبة نجاح،
أسباب مفصّلة).

## ⚠️ اقرأ هذا أولًا (صراحة كاملة)

1. **هذا المشروع نقطة انطلاق قوية، مش منتج نهائي جاهز للإنتاج.** بناء نظام بهذا
   الحجم (كل مدارس التحليل + بيانات حية + تعلم ذاتي + لوحة تحكم + تنفيذ) هو عمل
   فريق لأشهر، وليس شيئًا يُبنى كاملًا ومُختبرًا 100% في جلسة واحدة.
2. **"نسبة النجاح" ليست تنبؤًا مضمونًا.** قبل ما تسجّل 30 صفقة حقيقية على الأقل
   (`MIN_TRADES_BEFORE_TRAINING` في `config.py`)، الرقم اللي يظهر هو **درجة توافق
   مؤشرات** (rule-based confluence score) شفافة وواضحة الأسباب - مش احتمالًا
   إحصائيًا. بعد تسجيل صفقات كافية، يبدأ نموذج `RandomForest` فعليًا بالتعلّم من
   نتائجك الحقيقية (تم اختباره في هذا المشروع ويعمل).
3. **لا يوجد ضمان ربح.** أي نظام تحليل - مهما كان متقدمًا - لا يمكنه التنبؤ
   بالسوق بشكل مؤكد. استخدم حساب تجريبي (Demo) أولًا، وطبّق إدارة مخاطر صارمة
   (لا تخاطر بأكثر من 1-2% من رأس المال في الصفقة الواحدة).
4. **هذا ليس نصيحة مالية.** النظام أداة تحليل مساعدة على اتخاذ القرار، والقرار
   والمسؤولية النهائية عليك.

## ما تم بناؤه فعليًا وتم اختباره ✅

| الوحدة | الحالة |
|---|---|
| مؤشرات كلاسيكية (RSI, MACD, ATR, Bollinger, ADX, VWAP, MAs) | ✅ منطق حقيقي، **مُختبر بـ pytest** |
| هيكل السوق: Swing Points, BOS, CHoCH, MSS | ✅ منطق حقيقي، **مُختبر بـ pytest** |
| Order Blocks / Breaker Blocks / Mitigation Blocks | ✅ منطق حقيقي، مُختبر |
| Fair Value Gaps + Inverse FVG | ✅ منطق حقيقي، **مُختبر بـ pytest** |
| Liquidity Sweeps + Equal Highs/Lows | ✅ منطق حقيقي، **مُختبر بـ pytest** |
| تحليل متعدد الفريمات (MTF) + درجة توافق | ✅ منطق حقيقي، مُختبر |
| جلسات آسيا/لندن/نيويورك | ✅ يعمل (بحساب UTC) |
| فلتر الأخبار الاقتصادية | ⚠️ واجهة جاهزة، يحتاج ربط API خارجي (مثال Finnhub مرفق) |
| ارتباط الذهب/الدولار/العوائد | ✅ منطق حقيقي، مُختبر (يحتاج بيانات DXY فعلية من الوسيط) |
| محرك القرار النهائي (التقرير الكامل) | ✅ مُختبر - يولّد كل الحقول المطلوبة |
| التعلّم الذاتي (RandomForest حقيقي) | ✅ مُختبر فعليًا - يتدرب ويتنبأ، ويُخزَّن عبر StateStore (محلي أو GCS) |
| **طبقة تخزين موزّعة (StateStore)** | ✅ محلي (JSON) أو Firestore - قابلة للتبديل بمتغير بيئة واحد |
| **تسجيل JSON منظم (Cloud Logging جاهز)** | ✅ `logging_setup/logger.py` |
| **إدارة أسرار (Secret Manager + env fallback)** | ✅ `storage/secrets.py` |
| لوحة Streamlit | ✅ جاهزة، تعمل محليًا أو كخدمة Cloud Run مستقلة |
| اتصال MT5 حقيقي | ⚠️ الكود جاهز لكن يتطلب Windows + MT5 مثبّت (لا يمكن اختباره من بيئتي) |
| اتصال TradingView | ✅ Webhook حقيقي مُختبر (Flask + Firestore/محلي)، وضع `--mode tradingview` جاهز في main.py |
| **نشر GCP إنتاجي (Compute Engine + Cloud Run + Firestore)** | ✅ سكربتات جاهزة في `deploy/gcp/` - راجع `deploy/gcp/README.md` |
| **اختبارات آلية (pytest) + CI (GitHub Actions)** | ✅ 14 اختبار يمرّون بنجاح، يعمل تلقائيًا مع كل push |
| Elliott Wave / Wyckoff / Fibonacci الكاملة | ❌ لم تُبنَ بعد - هذه مدارس تعتمد على تفسير بشري بدرجة كبيرة، تحتاج نموذج منفصل (انظر "الخطوات التالية") |
| Volume Profile / Footprint | ❌ لم تُبنَ بعد - تحتاج بيانات Tick/Order Flow التي لا يوفرها MT5 القياسي |
| Backtesting تاريخي | ❌ لم يُبنَ بعد - **أهم خطوة ناقصة قبل استخدام مالي حقيقي** |

## هيكل المشروع

```
ai_trading_system/
├── config.py                      # كل الإعدادات القابلة للتعديل
├── main.py                        # حلقة التشغيل الحية (local/live/tradingview)
├── data_feed/mt5_connector.py     # اتصال MT5 حقيقي + وضع تجريبي Demo
├── data_feed/tradingview_feed.py  # قراءة شموع TradingView من التخزين المشترك
├── webhook/tradingview_webhook.py # استقبال بيانات TradingView (Flask، جاهز لـ Cloud Run)
├── indicators/technical.py        # RSI, MACD, ATR, Bollinger, ADX, VWAP...
├── smc/market_structure.py        # BOS/CHoCH/MSS, Order Blocks, FVG...
├── smc/liquidity.py               # Liquidity Sweeps
├── analysis/multi_timeframe.py    # تحليل متعدد الفريمات
├── analysis/sessions.py           # الجلسات + فلتر الأخبار
├── analysis/correlation.py        # الذهب/الدولار/العوائد
├── ml/self_learning.py            # التعلم الذاتي (RandomForest) - مبني على StateStore
├── engine/signal_engine.py        # محرك القرار النهائي (التقرير الكامل)
├── storage/state_store.py         # طبقة تخزين مجرّدة: محلي أو Firestore
├── storage/secrets.py             # جلب الأسرار: Secret Manager أو env vars
├── logging_setup/logger.py        # تسجيل JSON منظم (متوافق مع Cloud Logging)
├── dashboard/app.py               # لوحة Streamlit (تقرأ من StateStore)
├── tests/                         # 14 اختبار pytest حقيقي على المنطق الأساسي
├── deploy/gcp/                    # سكربتات نشر GCP كاملة (01 إلى 05)
├── Dockerfile / docker-compose.yml# تشغيل على أي جهاز فيه Docker
└── .github/workflows/tests.yml    # CI يشغّل الاختبارات تلقائيًا
```

## التشغيل السريع (تجربة بدون MT5 حقيقي)

```bash
pip install -r requirements.txt
python main.py --mode demo --loop --interval 30
```

في نافذة طرفية أخرى:
```bash
streamlit run dashboard/app.py
```

هذا يشغّل النظام كاملًا ببيانات صناعية واقعية الشكل عشان تشوف كل شيء يعمل
(التقرير، الأسباب، اللوحة) قبل ما تربطه ببيانات حقيقية.

## تشغيل الاختبارات

```bash
pip install pytest
pytest tests/ -v
```
14 اختبار يتحققون فعليًا من صحة المؤشرات وهيكل السوق على بيانات مصمَّمة خصيصًا
(zigzag واقعي، فجوات سعرية مزروعة، إلخ) - وليست اختبارات شكلية.

## النشر الإنتاجي على GCP (موصى به للتشغيل الجاد 24/7)

راجع **`deploy/gcp/README.md`** للمعمارية الكاملة والسكربتات الجاهزة
(Compute Engine + Cloud Run + Firestore + Secret Manager).

## التشغيل مع MT5 حقيقي

1. ثبّت MetaTrader 5 على Windows وسجّل دخول لحساب (يُفضّل Demo في البداية).
2. `pip install MetaTrader5`
3. عدّل `config.SYMBOLS` حسب رموز الوسيط عندك بالضبط (مثلًا قد يكون `XAUUSD.` أو
   `GOLD` حسب الوسيط).
4. شغّل: `python main.py --mode live --loop`

## التشغيل مع TradingView

TradingView لا توفر API عامًا لسحب الشموع مباشرة، لكن الربط عبر Webhook مُنفَّذ
بالكامل ومُختبر:

1. شغّل مستقبل الـ webhook محليًا: `python webhook/tradingview_webhook.py`
   (أو على GCP عبر `deploy/gcp/05_deploy_webhook_cloudrun.sh` للحصول على
   رابط HTTPS دائم بدون ngrok).
2. في TradingView، لكل فريم زمني تريد تغذيته (M5, M15, H1, H4, D1)، أنشئ
   Alert برسالة JSON بالشكل الموضّح أعلى `webhook/tradingview_webhook.py`،
   وضع رابط الـ webhook كـ Webhook URL.
3. شغّل النظام بوضع القراءة من TradingView: `python main.py --mode tradingview --loop`

## الخطوات التالية المقترحة (لو حابب تكمل المشروع بجدية)

1. **Backtesting حقيقي**: قبل أي استخدام فعلي، ابنِ محرك backtest يشغّل
   `signal_engine` على بيانات تاريخية ويقيس دقة كل عامل من عوامل `confluence_score`
   فعليًا - هذا هو الأساس الحقيقي لأي "نسبة نجاح" موثوقة، **وهو أهم بند ناقص حاليًا**.
2. **Wyckoff / Elliott Wave**: تحتاج تصنيف أنماط (pattern classification)، الأفضل
   بناؤها كنموذج منفصل يُدرَّب على أمثلة موسومة يدويًا، وليس قواعد ثابتة.
3. **إدارة مخاطر ديناميكية**: ربط حجم الصفقة (position sizing) بنسبة مئوية ثابتة
   من رأس المال بدل قيم ثابتة.
4. **تأمين اللوحة**: حاليًا `--allow-unauthenticated` على Cloud Run - فعّل
   Identity-Aware Proxy أو IAM invoker محدود قبل أي استخدام جدي.
5. **مراقبة وتنبيهات (Alerting)**: أضف Cloud Monitoring uptime check + تنبيه
   بريد/Slack لو توقف المحرك عن العمل.
6. **تنفيذ آلي (اختياري وحساس)**: أي ربط لتنفيذ صفقات تلقائيًا يحتاج طبقات أمان
   إضافية (حدود خسارة يومية، dead-man switch, إلخ) — لم يُبنَ هنا عمدًا لأن
   التنفيذ الآلي مسؤولية كبيرة ويجب بناؤه بحذر شديد ومنفصل عن محرك التحليل.

## الترخيص وإخلاء المسؤولية

هذا الكود لأغراض تعليمية وتطويرية. التداول في الأسواق المالية ينطوي على مخاطر
خسارة كاملة لرأس المال. المطوّر/المساعد غير مسؤول عن أي قرارات تداول تُتخذ
بناءً على هذا النظام.
