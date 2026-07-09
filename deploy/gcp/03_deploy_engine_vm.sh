#!/usr/bin/env bash
# deploy/gcp/03_deploy_engine_vm.sh
# ====================================
# يبني صورة Docker، يرفعها لـ Artifact Registry، وينشئ VM دائم (e2-small كافٍ
# لأعباء التحليل الحالية) يشغّل محرك التحليل 24/7 بوضع Firestore.
#
# الاستخدام:
#   export GCP_PROJECT_ID="your-project-id"
#   export GCP_REGION="us-central1"      # اختياري
#   ./03_deploy_engine_vm.sh
set -euo pipefail
: "${GCP_PROJECT_ID:?لازم تحدد GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-${REGION}-a}"
IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/trading-system/engine:latest"
SA_EMAIL="trading-system-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

cd "$(dirname "$0")/../.."   # رجوع لجذر المشروع

echo "==> بناء صورة Docker ورفعها..."
gcloud builds submit --tag "$IMAGE" .

echo "==> إنشاء/تحديث VM المحرك..."
if gcloud compute instances describe trading-engine-vm --zone="$ZONE" >/dev/null 2>&1; then
  gcloud compute instances add-metadata trading-engine-vm --zone="$ZONE" \
    --metadata=startup-script="$(cat deploy/gcp/startup-script.sh)",GCP_PROJECT_ID="$GCP_PROJECT_ID",GCP_REGION="$REGION"
  gcloud compute instances reset trading-engine-vm --zone="$ZONE"
else
  gcloud compute instances create trading-engine-vm \
    --zone="$ZONE" \
    --machine-type=e2-small \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --service-account="$SA_EMAIL" \
    --scopes=cloud-platform \
    --metadata=startup-script="$(cat deploy/gcp/startup-script.sh)",GCP_PROJECT_ID="$GCP_PROJECT_ID",GCP_REGION="$REGION"
fi

echo "==> تم. راقب اللوجات بـ:"
echo "    gcloud compute instances get-serial-port-output trading-engine-vm --zone=$ZONE"
