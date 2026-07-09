# النشر الإنتاجي على Google Cloud Platform (GCP)

## المعمارية

```
┌─────────────────────┐        ┌──────────────────────────┐
│  TradingView Alerts  │──POST─▶│  Cloud Run: trading-webhook│
│  (أو MT5 على VM      │        │  (سيرفرلس، HTTPS تلقائي)  │
│   ويندوز منفصل)       │        └──────────────┬───────────┘
└─────────────────────┘                        │ يكتب شموع
                                                 ▼
                                        ┌─────────────────┐
                                        │    Firestore     │◀── يقرأ الشموع
                                        │ (تخزين مشترك)     │    محرك التحليل
                                        └────────┬─────────┘
                                                  │ يقرأ/يكتب إشارات
                       ┌──────────────────────────┴──────────────────┐
                       ▼                                              ▼
          ┌─────────────────────────┐                  ┌──────────────────────┐
          │ Compute Engine VM:       │                  │ Cloud Run:            │
          │ trading-engine-vm        │                  │ trading-dashboard     │
          │ (main.py --loop دائم)    │                  │ (Streamlit، سيرفرلس)  │
          └─────────────────────────┘                  └──────────────────────┘
                       │
                       ▼
          ┌─────────────────────────┐
          │ Cloud Storage: نموذج ML  │
          │ (self_learning_model)    │
          └─────────────────────────┘
```

**لماذا هذا التصميم بالذات؟**
- **Firestore كتخزين مشترك**: بيسمح لخدمتين مستقلتين تمامًا (VM + Cloud Run) يشوفوا نفس البيانات لحظيًا بدون قرص مشترك - وهذا شرط أساسي لأي نظام موزّع حقيقي.
- **Cloud Run للوحة والـ webhook**: سيرفرلس، يتوسّع تلقائيًا، HTTPS مجاني، ولا يكلّفك شيء وقت عدم الاستخدام (min-instances=0).
- **Compute Engine للمحرك**: محرك التحليل يحتاج حلقة تشغيل مستمرة (loop)، وهذا نمط لا يناسب Cloud Run القياسي (مصمم لطلبات HTTP قصيرة)، لذلك VM دائم أنسب هنا.
- **Cloud Storage للنموذج**: Firestore غير مناسب لملفات ثنائية، فنموذج `RandomForest` المدرَّب يُخزَّن كـ blob في Bucket منفصل.

---

## الترتيب الصحيح للتنفيذ

### 1. المتطلبات الأساسية
```bash
# ثبّت gcloud CLI لو مش مثبّت: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud projects create your-project-id --name="AI Trading System"   # لو مشروع جديد
export GCP_PROJECT_ID="your-project-id"
```

### 2. إعداد المشروع (مرة واحدة فقط)
```bash
cd deploy/gcp
chmod +x *.sh
export GCP_PROJECT_ID="your-project-id"
./01_setup_project.sh
```
هذا يفعّل كل الخدمات المطلوبة، ينشئ Firestore، حساب خدمة بصلاحيات محدودة (مبدأ
أقل صلاحية)، Artifact Registry، وBucket للنموذج.

### 3. (اختياري) أسرار MT5 - لو محتاج بيانات MT5 حقيقية
```bash
./02_create_secrets.sh
```

### 4. نشر محرك التحليل (Compute Engine، يعمل 24/7)
```bash
./03_deploy_engine_vm.sh
```
يعمل افتراضيًا بوضع `demo` (لأن MT5 لا يعمل على Linux). لتفعيل TradingView
كمصدر بيانات حقيقي: عدّل الأمر داخل `startup-script.sh` من
`--mode demo` إلى `--mode tradingview` بعد نشر الـ webhook (خطوة 6).

### 5. نشر لوحة المعلومات (Cloud Run)
```bash
./04_deploy_dashboard_cloudrun.sh
```
هيطبع لك رابط HTTPS تقدر تفتحه من أي متصفح، بما فيه الموبايل، فورًا.

### 6. (لو هتستخدم TradingView) نشر مستقبل الـ Webhook
```bash
export WEBHOOK_TOKEN="اختر-قيمة-عشوائية-طويلة-وسرية"
./05_deploy_webhook_cloudrun.sh
```
هيطبع لك رابطًا مثل:
`https://trading-webhook-xxxxx.run.app/webhook/tradingview?token=xxxx`

انسخ هذا الرابط بالضبط في إعدادات كل Alert بـ TradingView (Webhook URL)،
مع رسالة الـ JSON الموضّحة في `webhook/tradingview_webhook.py`. لازم تعمل
Alert منفصل لكل فريم زمني تريد تغذيته (M5, M15, H1, H4, D1) حتى يعمل
التحليل متعدد الفريمات بكامل قوته.

---

## هل هذا "جاهز للإنتاج فعليًا 100%"؟ إجابة صريحة

**نعم بالنسبة لـ:**
- البنية السحابية نفسها (Firestore، Secret Manager، IAM بصلاحية محدودة،
  Cloud Run سيرفرلس، تسجيل JSON منظم لـ Cloud Logging) - هذه أنماط معمارية
  سليمة ومستخدمة فعليًا في الشركات.
- منطق التحليل الفني (SMC/ICT/المؤشرات) - مُختبر بـ 14 اختبار pytest يمر بنجاح.

**لأ بالنسبة لـ:**
- **الأمان**: `--allow-unauthenticated` على اللوحة يعني أي حد عنده الرابط
  يشوف تحليلاتك. للاستخدام الجدي، فعّل IAP (Identity-Aware Proxy) أو authentication
  حقيقي.
- **الموثوقية تحت الحمل**: لم يتم اختبار النظام تحت حمل حقيقي (عشرات الرموز،
  آلاف الطلبات/الثانية). VM واحد بحجم `e2-small` كافٍ للبداية فقط.
- **Backtesting**: لا يوجد بعد محرك يتحقق من دقة الإشارات تاريخيًا قبل الاعتماد
  عليها - **هذه أهم خطوة ناقصة قبل أي استخدام بمال حقيقي**.
- **التنبيهات (Alerting)**: لا يوجد حاليًا تنبيه تلقائي (بريد/SMS/Slack) لو
  توقف المحرك عن العمل فجأة - يُنصح بإضافة Cloud Monitoring uptime check.

---

## تكلفة تقريبية شهريًا (للتوجيه فقط، تحقق من الأسعار الفعلية)

| المكوّن | التقدير |
|---|---|
| Compute Engine e2-small (24/7) | ~13$ |
| Cloud Run (dashboard + webhook, استخدام خفيف) | 0-5$ (يتوسّع لصفر عند عدم الاستخدام) |
| Firestore (قراءة/كتابة بمعدل النظام الحالي) | 0-5$ |
| Cloud Storage (نموذج صغير) | أقل من 1$ |
| **الإجمالي التقريبي** | **~15-25$/شهر** |

---

## مراقبة النظام

```bash
# لوجات المحرك (Compute Engine)
gcloud compute instances get-serial-port-output trading-engine-vm --zone=$GCP_REGION-a

# لوجات Cloud Run
gcloud run services logs read trading-dashboard --region=$GCP_REGION
gcloud run services logs read trading-webhook --region=$GCP_REGION

# أو من الواجهة الرسومية مباشرة:
# https://console.cloud.google.com/logs
```
