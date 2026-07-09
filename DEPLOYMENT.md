# دليل التشغيل على أي منصة (DEPLOYMENT)

النقطة الحرجة الوحيدة في "أي منصة": **مكتبة MetaTrader5 الرسمية تعمل فقط على
Windows.** كل باقي النظام (التحليل، التعلم الذاتي، اللوحة) بايثون خالص ويعمل
على أي نظام تشغيل. إذًا القرار الأول هو: هل محتاج بيانات MT5 حقيقية أم لأ؟

---

## 1) عندك Windows وبتستخدم MT5 فعليًا → شغّله مباشرة (بدون Docker)

هذا هو المسار الوحيد للبيانات الحية عبر MT5:

```powershell
pip install -r requirements.txt
pip install MetaTrader5
python main.py --mode live --loop --interval 30
```

وفي نافذة PowerShell أخرى:
```powershell
streamlit run dashboard/app.py
```

---

## 2) عندك Mac / Linux (لابتوب شخصي) → وضع Demo أو TradingView Webhook

MT5 الرسمية لن تعمل، لكن كل شيء آخر يعمل 100%:

```bash
pip install -r requirements.txt
python main.py --mode demo --loop --interval 30       # بيانات تجريبية فورًا
# أو، للبيانات الحقيقية عبر TradingView:
python webhook/tradingview_webhook.py                  # يستقبل Alerts
```

```bash
streamlit run dashboard/app.py
```

---

## 3) أي منصة عبر Docker (الأسهل والأكثر "يعمل على أي جهاز")

يحتاج فقط تثبيت Docker Desktop (Windows/Mac) أو Docker Engine (Linux):

```bash
docker compose up --build
```

هذا يشغّل تلقائيًا:
- `engine` → محرك التحليل (وضع demo افتراضيًا)
- `dashboard` → متاح على `http://localhost:8501`
- `webhook` (اختياري) → `docker compose --profile tradingview up`

لتشغيله بوضع "live" مع MT5: **لا يمكن داخل Docker** (نفس قيد Windows)، إلا لو
استخدمت Windows Container خاص أو Wine (غير مضمون الاستقرار). الأفضل: شغّل
`engine` على Windows مباشرة، وخلي الـ `dashboard` وحده يعمل بـ Docker على أي
جهاز آخر ويقرأ نفس مجلد `data/` (مشترك عبر شبكة أو مزامنة ملفات).

---

## 4) سيرفر سحابي للتشغيل المستمر 24/7

### أ) Google Cloud Platform (GCP) - نشر إنتاجي كامل (موصى به)

راجع الدليل المخصص والمفصّل: **`deploy/gcp/README.md`**

هذا مسار إنتاجي حقيقي وليس مجرد VPS عام: Compute Engine للمحرك المستمر +
Cloud Run سيرفرلس للوحة والـ webhook + Firestore كتخزين مشترك بين الخدمات +
Secret Manager للأسرار + IAM بصلاحيات محدودة. فيه سكربتات جاهزة مرقّمة
(01 إلى 05) تنفّذها بالترتيب وتبني بيئة كاملة من الصفر.

### ب) VPS لينكس عادي (Ubuntu) - بديل أبسط وأرخص
مناسب لو مش محتاج MT5 حقيقي (يعتمد على TradingView Webhook أو Demo):

```bash
sudo apt update && sudo apt install python3-pip python3-venv -y
git clone <your-repo-or-upload-files> /opt/ai_trading_system
cd /opt/ai_trading_system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

بعدها فعّل خدمات النظام الدائمة (تشتغل حتى لو أعدت تشغيل السيرفر):
راجع `deploy/systemd_services.txt` وانسخ الملفين لـ `/etc/systemd/system/`، ثم:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now trading-engine trading-dashboard
```

افتح المنفذ 8501 في الفايروول (`ufw allow 8501`) وادخل اللوحة من
`http://<server-ip>:8501`.

### ج) VPS ويندوز (لو محتاج MT5 حقيقي فعليًا 24/7 بدون GCP)
مزودات مثل Azure/AWS/Vultr توفر Windows Server VPS. ثبّت عليه MT5 + بايثون
بنفس خطوات القسم (1)، وشغّل `main.py` كـ Scheduled Task أو خدمة عبر NSSM
(Non-Sucking Service Manager) عشان يفضل شغّال دايمًا.

---

## 5) الوصول من الموبايل

النظام نفسه (main.py) لا يشتغل على الموبايل، لكن **لوحة Streamlit موقع ويب
عادي** - بمجرد ما تشغّلها على أي سيرفر (VPS/Docker)، تقدر تفتحها من متصفح
موبايلك عادي على نفس الرابط `http://<server-ip>:8501`.

---

## ملخص سريع: أي مسار تختار؟

| وضعك | الحل الأنسب |
|---|---|
| عندي Windows وحساب MT5 حقيقي | مسار (1) مباشرة، بدون Docker |
| عندي Mac/Linux وحابب أجرب بسرعة | مسار (2) وضع demo |
| عايز أشغّله بسهولة على أي جهاز بدون تعقيد | مسار (3) Docker |
| عايز يشتغل 24/7 حتى وجهازي مقفول (بأبسط شكل) | مسار (4-ب) VPS + systemd أو Docker |
| عايز نشر إنتاجي حقيقي وقابل للتوسع | مسار (4-أ) GCP - راجع `deploy/gcp/README.md` |
| عايز أوصله من موبايلي | شغّل اللوحة على أي سيرفر (4)، افتحها من متصفح الموبايل |
