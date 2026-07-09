"""
storage/state_store.py
========================
طبقة تخزين مجرّدة (Storage Abstraction). بدل ما يكتب main.py مباشرة في ملف
JSON محلي (اللي بيفشل بمجرد ما تشغّل engine وdashboard على خدمتين منفصلتين
في السحابة - كل خدمة عندها قرصها الخاص)، كل الكود يتعامل مع واجهة StateStore
واحدة، وتقدر تبدّل الخلفية الفعلية بمتغير بيئة واحد:

    STORE_BACKEND=local      -> ملفات محلية (افتراضي، للتطوير)
    STORE_BACKEND=firestore  -> Google Cloud Firestore (للإنتاج على GCP)

هذا هو الأساس اللي بيخلي engine (شغّال على VM) وdashboard (شغّال على Cloud Run
منفصل تمامًا) يشوفوا نفس البيانات لحظيًا بدون أي قرص مشترك.
"""
from __future__ import annotations
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from logging_setup.logger import get_logger

logger = get_logger(__name__)


class StateStore(ABC):
    @abstractmethod
    def save_signal(self, symbol: str, report: dict) -> None: ...

    @abstractmethod
    def get_signal(self, symbol: str) -> Optional[dict]: ...

    @abstractmethod
    def get_all_signals(self) -> dict: ...

    @abstractmethod
    def log_trade(self, features: dict, outcome: Optional[str] = None) -> str:
        """يرجع معرّف الصفقة (trade_id) لاستخدامه لاحقًا في update_trade_outcome."""
        ...

    @abstractmethod
    def update_trade_outcome(self, trade_id: str, outcome: str) -> bool: ...

    @abstractmethod
    def get_labeled_trades(self) -> list: ...

    @abstractmethod
    def save_model_bytes(self, model_bytes: bytes) -> None: ...

    @abstractmethod
    def load_model_bytes(self) -> Optional[bytes]: ...


# ---------------------------------------------------------------------------
# التطبيق المحلي - ملفات JSON/CSV (بيئة التطوير، أو نشر بسيط بخادم واحد)
# ---------------------------------------------------------------------------
class LocalFileStore(StateStore):
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.signals_path = os.path.join(base_dir, "latest_signals.json")
        self.trades_path = os.path.join(base_dir, "trade_log.jsonl")
        self.model_path = os.path.join(base_dir, "self_learning_model.joblib")

    def _read_signals(self) -> dict:
        if not os.path.exists(self.signals_path):
            return {}
        with open(self.signals_path, "r") as f:
            return json.load(f)

    def save_signal(self, symbol: str, report: dict) -> None:
        data = self._read_signals()
        data[symbol] = report
        with open(self.signals_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def get_signal(self, symbol: str) -> Optional[dict]:
        return self._read_signals().get(symbol)

    def get_all_signals(self) -> dict:
        return self._read_signals()

    def log_trade(self, features: dict, outcome: Optional[str] = None) -> str:
        trade_id = f"{datetime.now(timezone.utc).timestamp():.6f}"
        row = {"trade_id": trade_id, "timestamp": datetime.now(timezone.utc).isoformat(),
               "outcome": outcome, **features}
        with open(self.trades_path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return trade_id

    def update_trade_outcome(self, trade_id: str, outcome: str) -> bool:
        if not os.path.exists(self.trades_path):
            return False
        rows = []
        found = False
        with open(self.trades_path, "r") as f:
            for line in f:
                row = json.loads(line)
                if row["trade_id"] == trade_id:
                    row["outcome"] = outcome
                    found = True
                rows.append(row)
        if found:
            with open(self.trades_path, "w") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return found

    def get_labeled_trades(self) -> list:
        if not os.path.exists(self.trades_path):
            return []
        rows = []
        with open(self.trades_path, "r") as f:
            for line in f:
                row = json.loads(line)
                if row.get("outcome") in ("win", "loss"):
                    rows.append(row)
        return rows

    def save_model_bytes(self, model_bytes: bytes) -> None:
        with open(self.model_path, "wb") as f:
            f.write(model_bytes)

    def load_model_bytes(self) -> Optional[bytes]:
        if not os.path.exists(self.model_path):
            return None
        with open(self.model_path, "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# تطبيق Firestore - الإنتاج على GCP
# ---------------------------------------------------------------------------
class FirestoreStore(StateStore):
    """
    يتطلب: pip install google-cloud-firestore
    والمصادقة عبر Application Default Credentials (تلقائي على Compute Engine/
    Cloud Run بحساب الخدمة المرفق، أو GOOGLE_APPLICATION_CREDENTIALS محليًا).
    Firestore غير مناسب لتخزين ملفات ثنائية كبيرة (نموذج ML) مباشرة، لذلك
    نستخدم Cloud Storage للنموذج، وFirestore فقط للبيانات النصية/JSON.
    """

    def __init__(self, project_id: Optional[str] = None, gcs_bucket: Optional[str] = None):
        try:
            from google.cloud import firestore
        except ImportError as e:
            raise RuntimeError(
                "مكتبة google-cloud-firestore غير مثبّتة. شغّل: pip install google-cloud-firestore"
            ) from e
        self._firestore = firestore
        self.client = firestore.Client(project=project_id)
        self.gcs_bucket = gcs_bucket or os.environ.get("GCS_MODEL_BUCKET")
        self._gcs_client = None
        logger.info("firestore_store_initialized", extra={"project_id": project_id, "gcs_bucket": self.gcs_bucket})

    def save_signal(self, symbol: str, report: dict) -> None:
        self.client.collection("signals").document(symbol).set(report)

    def get_signal(self, symbol: str) -> Optional[dict]:
        doc = self.client.collection("signals").document(symbol).get()
        return doc.to_dict() if doc.exists else None

    def get_all_signals(self) -> dict:
        docs = self.client.collection("signals").stream()
        return {d.id: d.to_dict() for d in docs}

    def log_trade(self, features: dict, outcome: Optional[str] = None) -> str:
        doc_ref = self.client.collection("trades").document()
        doc_ref.set({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome, **features,
        })
        return doc_ref.id

    def update_trade_outcome(self, trade_id: str, outcome: str) -> bool:
        doc_ref = self.client.collection("trades").document(trade_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.update({"outcome": outcome})
        return True

    def get_labeled_trades(self) -> list:
        docs = self.client.collection("trades").where("outcome", "in", ["win", "loss"]).stream()
        return [d.to_dict() for d in docs]

    def _gcs(self):
        if self._gcs_client is None:
            from google.cloud import storage
            self._gcs_client = storage.Client()
        return self._gcs_client

    def save_model_bytes(self, model_bytes: bytes) -> None:
        if not self.gcs_bucket:
            raise RuntimeError("GCS_MODEL_BUCKET غير مُعرَّف - لازم لتخزين النموذج على GCP")
        bucket = self._gcs().bucket(self.gcs_bucket)
        blob = bucket.blob("self_learning_model.joblib")
        blob.upload_from_string(model_bytes)

    def load_model_bytes(self) -> Optional[bytes]:
        if not self.gcs_bucket:
            return None
        bucket = self._gcs().bucket(self.gcs_bucket)
        blob = bucket.blob("self_learning_model.joblib")
        if not blob.exists():
            return None
        return blob.download_as_bytes()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_store() -> StateStore:
    backend = os.environ.get("STORE_BACKEND", "local").lower()
    if backend == "firestore":
        logger.info("using_firestore_backend")
        return FirestoreStore(
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            gcs_bucket=os.environ.get("GCS_MODEL_BUCKET"),
        )
    logger.info("using_local_backend")
    return LocalFileStore(base_dir=os.environ.get("LOCAL_DATA_DIR", "data"))
