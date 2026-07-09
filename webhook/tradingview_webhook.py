"""
webhook/tradingview_webhook.py (production version)
======================================================
يستقبل تنبيهات (Alerts) من TradingView عبر Pine Script webhook، ويخزّن كل
شمعة عبر StateStore (محليًا أو Firestore) - نفس الطبقة اللي يستخدمها main.py
والداشبورد، عشان أي بيانات توصل هنا تبقى متاحة فورًا لمحرك التحليل بغض النظر
عن مكان تشغيله.

مثال Alert Message في TradingView (Pine Script alertcondition / alert()):
{
  "symbol": "XAUUSD",
  "timeframe": "15",
  "time": "{{time}}",
  "open": "{{open}}", "high": "{{high}}", "low": "{{low}}", "close": "{{close}}",
  "volume": "{{volume}}"
}

التشغيل محليًا:
    python webhook/tradingview_webhook.py

التشغيل على Cloud Run: راجع deploy/gcp/05_deploy_webhook_cloudrun.sh
(Cloud Run يحدد المنفذ عبر متغير البيئة PORT تلقائيًا)
"""
import os
from flask import Flask, request, jsonify

from storage.state_store import get_store
from logging_setup.logger import get_logger

app = Flask(__name__)
store = get_store()
logger = get_logger("tradingview_webhook")

# سر بسيط للتحقق من مصدر الطلب (ضعه كـ query param في رابط الـ Alert في
# TradingView: https://.../webhook/tradingview?token=xxxx). ليس بديلاً عن
# مصادقة حقيقية لو الرابط عام بالكامل، لكنه يمنع الطلبات العشوائية الشائعة.
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")


@app.route("/webhook/tradingview", methods=["POST"])
def tradingview_webhook():
    if WEBHOOK_TOKEN and request.args.get("token") != WEBHOOK_TOKEN:
        logger.warning("webhook_unauthorized_attempt", extra={"remote_addr": request.remote_addr})
        return jsonify({"status": "error", "message": "غير مصرّح"}), 401

    payload = request.get_json(force=True, silent=True)
    if not payload or "symbol" not in payload or "timeframe" not in payload:
        return jsonify({"status": "error", "message": "Payload غير صالح - يلزم symbol و timeframe"}), 400

    try:
        candle = {
            "time": payload["time"], "open": float(payload["open"]), "high": float(payload["high"]),
            "low": float(payload["low"]), "close": float(payload["close"]),
            "volume": float(payload.get("volume", 0)),
        }
    except (KeyError, ValueError) as e:
        return jsonify({"status": "error", "message": f"بيانات شمعة غير صالحة: {e}"}), 400

    key = f"tv_{payload['symbol']}_{payload['timeframe']}"
    # نستخدم نفس واجهة save_signal كتخزين عام key-value مؤقت للشموع الواردة؛
    # محرك التحليل (data_feed) يقرأها لاحقًا بنفس المفتاح.
    existing = store.get_signal(key) or {"candles": []}
    existing["candles"].append(candle)
    existing["candles"] = existing["candles"][-1000:]  # الاحتفاظ بآخر 1000 شمعة فقط
    store.save_signal(key, existing)

    logger.info("tradingview_candle_received", extra={"symbol": payload["symbol"], "timeframe": payload["timeframe"]})
    return jsonify({"status": "ok"}), 200


@app.route("/healthz", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    app.run(host="0.0.0.0", port=port)
