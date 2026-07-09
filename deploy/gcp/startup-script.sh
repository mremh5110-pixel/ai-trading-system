#!/usr/bin/env bash
# deploy/gcp/startup-script.sh
# ==============================
# يُمرَّر تلقائيًا لـ Compute Engine كـ startup-script. يثبّت Docker (لو مش
# موجود)، يسحب صورة النظام من Artifact Registry، ويشغّل المحرك مع
# STORE_BACKEND=firestore عشان يكتب البيانات اللي تقدر لوحة Cloud Run تقرأها
# مباشرة.
set -euo pipefail

if ! command -v docker &>/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io
fi

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/trading-system/engine:latest"
docker pull "$IMAGE"

docker rm -f trading-engine 2>/dev/null || true
docker run -d --name trading-engine --restart unless-stopped \
  -e STORE_BACKEND=firestore \
  -e GOOGLE_CLOUD_PROJECT="${GCP_PROJECT_ID}" \
  -e GCS_MODEL_BUCKET="${GCP_PROJECT_ID}-trading-model" \
  "$IMAGE" python main.py --mode demo --loop --interval 30
  # ملاحظة: --mode demo هنا لأن مكتبة MT5 لا تعمل على Linux.
  # لو محتاج بيانات MT5 حقيقية: استخدم Windows VM (راجع deploy/gcp/README.md)
  # أو بدّل --mode بمصدر بيانات TradingView Webhook.
