"""
logging_setup/logger.py
========================
تسجيل منظم (structured logging) بصيغة JSON - تُقرأ تلقائيًا وبشكل صحيح بواسطة
Cloud Logging على GCP (كل سطر JSON يُفهرس كحقول منفصلة، مش نص عشوائي).
يعمل محليًا أيضًا (يطبع JSON عادي في الطرفية) بدون أي اعتماديات إضافية على
Google Cloud SDK - عشان تقدر تطوّر وتختبر محليًا بنفس نظام اللوجات بالظبط.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # أي حقول إضافية مُمررة عبر extra={...}
        for key, value in record.__dict__.items():
            if key not in ("args", "msg", "levelname", "levelno", "pathname", "filename",
                           "module", "exc_info", "exc_text", "stack_info", "lineno",
                           "funcName", "created", "msecs", "relativeCreated", "thread",
                           "threadName", "processName", "process", "name", "message"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    pass
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:  # لا تكرر إضافة handlers لو تم استدعاؤها أكثر من مرة
        return logger
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
