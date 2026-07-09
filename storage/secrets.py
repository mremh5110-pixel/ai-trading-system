"""
storage/secrets.py
====================
جلب الأسرار (بيانات دخول MT5، مفاتيح API) من Google Secret Manager في الإنتاج،
مع fallback لمتغيرات البيئة (.env) في التطوير المحلي - نفس الكود يعمل في
الحالتين بدون أي تعديل.

الاستخدام على GCP:
    gcloud secrets create mt5-login --data-file=- <<< "12345678"
    gcloud secrets create mt5-password --data-file=- <<< "your-password"
    gcloud secrets create mt5-server --data-file=- <<< "YourBroker-Live"
    # وامنح حساب الخدمة صلاحية secretmanager.secretAccessor

الاستخدام محليًا: عرّف نفس الأسماء كمتغيرات بيئة (MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
"""
import os
from typing import Optional

from logging_setup.logger import get_logger

logger = get_logger(__name__)

_secret_client = None


def _get_secret_manager_client():
    global _secret_client
    if _secret_client is None:
        from google.cloud import secretmanager
        _secret_client = secretmanager.SecretManagerServiceClient()
    return _secret_client


def get_secret(name: str, env_fallback_name: Optional[str] = None) -> Optional[str]:
    """
    name: اسم السر داخل Secret Manager (مثل 'mt5-login')
    env_fallback_name: اسم متغير البيئة البديل للتطوير المحلي (مثل 'MT5_LOGIN')
    """
    env_name = env_fallback_name or name.upper().replace("-", "_")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if project_id:
        try:
            client = _get_secret_manager_client()
            secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning("secret_manager_fetch_failed", extra={"secret": name, "error": str(e)})

    value = os.environ.get(env_name)
    if value is None:
        logger.warning("secret_not_found_anywhere", extra={"secret": name, "env_fallback": env_name})
    return value


def get_mt5_credentials() -> dict:
    return {
        "login": get_secret("mt5-login", "MT5_LOGIN"),
        "password": get_secret("mt5-password", "MT5_PASSWORD"),
        "server": get_secret("mt5-server", "MT5_SERVER"),
    }
