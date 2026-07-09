#!/usr/bin/env bash
# deploy/gcp/04_deploy_dashboard_cloudrun.sh
# =============================================
# ينشر لوحة Streamlit كخدمة Cloud Run مستقلة تمامًا عن VM المحرك، وتقرأ نفس
# البيانات لحظيًا عبر Firestore. هذا هو الجزء اللي هتفتح رابطه من أي متصفح
# (بما فيه الموبايل).
#
# الاستخدام:
#   export GCP_PROJECT_ID="your-project-id"
#   ./04_deploy_dashboard_cloudrun.sh
set -euo pipefail
: "${GCP_PROJECT_ID:?لازم تحدد GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/trading-system/dashboard:latest"
SA_EMAIL="trading-system-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

cd "$(dirname "$0")/../.."

echo "==> بناء صورة اللوحة ورفعها..."
gcloud builds submit --tag "$IMAGE" -f deploy/gcp/Dockerfile.dashboard .

echo "==> نشر الخدمة على Cloud Run..."
gcloud run deploy trading-dashboard \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --service-account="$SA_EMAIL" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${GCP_PROJECT_ID},GCS_MODEL_BUCKET=${GCP_PROJECT_ID}-trading-model" \
  --min-instances=0 \
  --max-instances=3 \
  --memory=512Mi \
  --allow-unauthenticated

echo "==> تم النشر. رابط اللوحة:"
gcloud run services describe trading-dashboard --region="$REGION" --format='value(status.url)'

echo ""
echo "⚠️ ملاحظة أمان: --allow-unauthenticated يخلي اللوحة مرئية لأي حد عنده"
echo "   الرابط. لو محتاج حمايتها، شيل هذا الفلاج وفعّل Identity-Aware Proxy"
echo "   أو IAM invoker permissions محدودة بدل ما تفتحها للعامة."
