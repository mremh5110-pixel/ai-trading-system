#!/usr/bin/env bash
# deploy/gcp/01_setup_project.sh
# ================================
# يجهّز مشروع GCP من الصفر: يفعّل الخدمات، ينشئ حساب خدمة، Firestore، وSecret
# Manager للأسرار. شغّله مرة واحدة فقط عند البدء.
#
# الاستخدام:
#   export GCP_PROJECT_ID="your-project-id"
#   ./01_setup_project.sh
set -euo pipefail

: "${GCP_PROJECT_ID:?لازم تحدد GCP_PROJECT_ID أولًا: export GCP_PROJECT_ID=your-project-id}"
REGION="${GCP_REGION:-us-central1}"

echo "==> تفعيل الخدمات المطلوبة..."
gcloud config set project "$GCP_PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  logging.googleapis.com

echo "==> إنشاء قاعدة بيانات Firestore (Native mode) في $REGION..."
gcloud firestore databases create --location="$REGION" --type=firestore-native || \
  echo "    (Firestore موجودة بالفعل - تم تجاهل هذه الخطوة)"

echo "==> إنشاء حساب خدمة مخصص للنظام..."
SA_NAME="trading-system-sa"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="AI Trading System Service Account" || \
  echo "    (حساب الخدمة موجود بالفعل - تم تجاهل هذه الخطوة)"

echo "==> منح الصلاحيات اللازمة فقط (مبدأ أقل صلاحية ممكنة)..."
for ROLE in roles/datastore.user roles/secretmanager.secretAccessor roles/storage.objectAdmin roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None \
    --quiet
done

echo "==> إنشاء Artifact Registry repo لصور Docker..."
gcloud artifacts repositories create trading-system \
  --repository-format=docker \
  --location="$REGION" || echo "    (موجود بالفعل)"

echo "==> إنشاء Bucket لتخزين نموذج التعلم الذاتي..."
GCS_BUCKET="${GCP_PROJECT_ID}-trading-model"
gcloud storage buckets create "gs://${GCS_BUCKET}" --location="$REGION" || echo "    (موجود بالفعل)"

cat <<EOF

==================================================================
تم الإعداد الأساسي بنجاح. القيم التي هتحتاجها في باقي السكربتات:

  export GCP_PROJECT_ID="${GCP_PROJECT_ID}"
  export GCP_REGION="${REGION}"
  export GCS_MODEL_BUCKET="${GCS_BUCKET}"
  export SA_EMAIL="${SA_EMAIL}"

الخطوة التالية: أضف أسرار MT5 (لو محتاج بيانات حية حقيقية) عبر:
  ./02_create_secrets.sh
==================================================================
EOF
