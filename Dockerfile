# يشغّل النظام (main.py + dashboard) على أي جهاز فيه Docker: Windows, Mac,
# Linux, أو أي VPS سحابي — بدون القلق من اختلاف إصدارات Python أو المكتبات.
#
# ⚠️ ملاحظة مهمة: هذا الـ Docker image يعمل بوضع "demo" أو مع TradingView
# Webhook فقط. مكتبة MetaTrader5 الرسمية لا تعمل على Linux (أساس صورة Docker)
# لأنها مبنية فقط لويندوز. لو محتاج بيانات MT5 حقيقية، شغّل main.py مباشرة
# على Windows (بدون Docker) - راجع قسم "MT5 على Windows" في DEPLOYMENT.md

FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات أولًا (طبقة منفصلة تُسرّع إعادة البناء)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8501 5005

CMD ["python", "main.py", "--mode", "demo", "--loop", "--interval", "30"]
