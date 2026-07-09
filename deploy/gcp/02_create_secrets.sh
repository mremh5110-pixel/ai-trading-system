#!/usr/bin/env bash
# deploy/gcp/02_create_secrets.sh
# ==================================
# يخزّن بيانات دخول MT5 بأمان في Secret Manager بدل كتابتها في أي كود أو ملف.
# شغّله فقط لو ناوي تستخدم --mode live مع MT5 حقيقي.
#
# الاستخدام:
#   export GCP_PROJECT_ID="your-project-id"
#   ./02_create_secrets.sh
set -euo pipefail
: "${GCP_PROJECT_ID:?لازم تحدد GCP_PROJECT_ID أولًا}"

create_or_update_secret () {
  local name="$1"
  local prompt="$2"
  read -rsp "$prompt: " value
  echo
  if gcloud secrets describe "$name" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --project="$GCP_PROJECT_ID" --data-file=-
  else
    printf '%s' "$value" | gcloud secrets create "$name" --project="$GCP_PROJECT_ID" --data-file=-
  fi
}

create_or_update_secret "mt5-login"    "MT5 Login (رقم الحساب)"
create_or_update_secret "mt5-password" "MT5 Password"
create_or_update_secret "mt5-server"   "MT5 Server (مثل YourBroker-Live)"

echo "==> تم حفظ الأسرار الثلاثة في Secret Manager بنجاح."
