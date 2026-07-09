#!/usr/bin/env bash
# deploy/gcp/05_deploy_webhook_cloudrun.sh
# ===========================================
# ينشر مستقبل TradingView Webhook كخدمة Cloud Run - رابط HTTPS ثابت وجاهز
# مباشرة للصقه في إعدادات Alert داخل TradingView (بدون الحاجة لـ ngrok أو أي
# شيء مؤقت).
#
# الاستخدام:
#   export GCP_PROJECT_ID="your-project-id"
#   export WEBHOOK_TOKEN="اختر-قيمة-سرية-عشوائية-طويلة"
#   ./05_deploy_webhook_cloudrun.sh
set -euo pipefail
: "${GCP_PROJECT_ID:?لازم تحدد GCP_PROJECT_ID}"
: "${WEBHOOK_TOKEN:?لازم تحدد WEBHOOK_TOKEN (قيمة سرية تمنع طلبات عشوائية على الرابط العام)}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/trading-system/webhook:latest"
SA_EMAIL="trading-system-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

cd "$(dirname "$0")/../.."

cat > deploy/gcp/Dockerfile.webhook <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-gcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-gcp.txt
COPY . .
ENV STORE_BACKEND=firestore
EXPOSE 8080
CMD ["python", "webhook/tradingview_webhook.py"]
EOF

echo "==> بناء صورة الـ webhook ورفعها..."
gcloud builds submit --tag "$IMAGE" -f deploy/gcp/Dockerfile.webhook .

echo "==> نشر الخدمة على Cloud Run..."
gcloud run deploy trading-webhook \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --service-account="$SA_EMAIL" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},GCS_MODEL_BUCKET=${GCP_PROJECT_ID}-trading-model,WEBHOOK_TOKEN=${WEBHOOK_TOKEN},PORT=8080" \
  --min-instances=0 \
  --max-instances=5 \
  --memory=256Mi \
  --allow-unauthenticated

URL=$(gcloud run services describe trading-webhook --region="$REGION" --format='value(status.url)')
echo ""
echo "==> تم النشر. استخدم هذا الرابط بالضبط في إعدادات Alert بـ TradingView:"
echo "    ${URL}/webhook/tradingview?token=${WEBHOOK_TOKEN}"
