"""
ml/self_learning.py (v2 - storage-backed)
==========================================
نفس منطق التعلم الذاتي السابق، لكن مبني على StateStore بدل الوصول المباشر
لملفات CSV - عشان يعمل بنفس الطريقة تمامًا محليًا أو موزّعًا على GCP
(Compute Engine يكتب، Cloud Run Job يدرّب، النتيجة تُقرأ من أي مكان).

⚠️ نفس الملاحظة الجوهرية من النسخة السابقة: النموذج لا يملك قدرة تنبؤية
حقيقية إلا بعد MIN_TRADES_BEFORE_TRAINING صفقة حقيقية مسجّلة. قبل ذلك
"نسبة النجاح" تُبنى من confluence_score القاعدي الشفاف فقط.
"""
import io
from typing import Optional

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

from storage.state_store import StateStore
from logging_setup.logger import get_logger

logger = get_logger(__name__)

FEATURE_COLUMNS = [
    "alignment_score", "rsi", "adx", "atr_ratio_to_price", "confluence_score",
    "num_confluences", "session_score", "has_liquidity_sweep", "has_fvg",
    "has_order_block", "risk_reward",
]


class SelfLearningEngine:
    def __init__(self, store: StateStore, min_trades_before_training: int = 30, retrain_every: int = 10):
        self.store = store
        self.min_trades = min_trades_before_training
        self.retrain_every = retrain_every
        self.model = self._load_model()

    # -------------------------------------------------------------- logging
    def log_trade(self, features: dict, outcome: Optional[str] = None) -> str:
        trade_id = self.store.log_trade(features, outcome)
        logger.info("trade_logged", extra={"trade_id": trade_id, "outcome": outcome})
        return trade_id

    def update_trade_outcome(self, trade_id: str, outcome: str) -> bool:
        ok = self.store.update_trade_outcome(trade_id, outcome)
        logger.info("trade_outcome_updated", extra={"trade_id": trade_id, "outcome": outcome, "found": ok})
        return ok

    # -------------------------------------------------------------- training
    def _load_model(self):
        raw = self.store.load_model_bytes()
        if raw is None:
            return None
        try:
            return joblib.load(io.BytesIO(raw))
        except Exception as e:
            logger.warning("model_load_failed", extra={"error": str(e)})
            return None

    def _labeled_dataframe(self) -> pd.DataFrame:
        rows = self.store.get_labeled_trades()
        if not rows:
            return pd.DataFrame(columns=FEATURE_COLUMNS + ["outcome"])
        return pd.DataFrame(rows)

    def should_retrain(self) -> bool:
        df = self._labeled_dataframe()
        if len(df) < self.min_trades:
            return False
        return len(df) % self.retrain_every == 0

    def train(self, force: bool = False) -> dict:
        df = self._labeled_dataframe()
        if len(df) < self.min_trades and not force:
            return {"trained": False,
                    "reason": f"يحتاج {self.min_trades} صفقة مسجلة على الأقل (متوفر حاليًا: {len(df)})"}

        for col in FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0
        X = df[FEATURE_COLUMNS].fillna(0)
        y = (df["outcome"] == "win").astype(int)

        model = RandomForestClassifier(
            n_estimators=200, max_depth=6, min_samples_leaf=5,
            class_weight="balanced", random_state=42,
        )
        model.fit(X, y)

        buf = io.BytesIO()
        joblib.dump(model, buf)
        self.store.save_model_bytes(buf.getvalue())
        self.model = model

        importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.round(3).tolist()))
        logger.info("model_trained", extra={"num_trades_used": len(df), "feature_importances": importances})
        return {"trained": True, "num_trades_used": len(df), "feature_importances": importances}

    # -------------------------------------------------------------- inference
    def predict_win_probability(self, features: dict) -> dict:
        if self.model is None:
            return {
                "probability": None, "source": "rule_based_only",
                "note": "لا يوجد نموذج مدرَّب بعد - يُستخدم confluence_score كبديل مؤقت",
            }
        X = pd.DataFrame([{k: features.get(k, 0) for k in FEATURE_COLUMNS}])
        proba = self.model.predict_proba(X)[0]
        classes = list(self.model.classes_)
        win_idx = classes.index(1) if 1 in classes else None
        p_win = float(proba[win_idx]) if win_idx is not None else None
        return {"probability": p_win, "source": "ml_model", "note": "مبني على صفقاتك التاريخية المسجلة"}
