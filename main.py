"""
main.py (production version)
==============================
حلقة التشغيل الحية. الفرق عن النسخة الأولى: يكتب/يقرأ عبر StateStore (محلي أو
Firestore) بدل ملف JSON مباشر، يستخدم تسجيل JSON منظم، ويجلب بيانات دخول MT5
من Secret Manager في الإنتاج.

التشغيل محليًا (بدون أي إعداد GCP):
    python main.py --mode demo --loop

التشغيل على GCP (بعد ضبط متغيرات البيئة GOOGLE_CLOUD_PROJECT, STORE_BACKEND=firestore):
    python main.py --mode live --loop
"""
import argparse
import time
from datetime import datetime, timezone

import config
from data_feed import mt5_connector as feed
from data_feed import tradingview_feed
from analysis.correlation import analyze_correlations
from ml.self_learning import SelfLearningEngine
from engine.signal_engine import generate_trade_report
from storage.state_store import get_store
from storage.secrets import get_mt5_credentials
from logging_setup.logger import get_logger

logger = get_logger("main")


def run_once(symbol: str, mode: str, sl_engine: SelfLearningEngine, store):
    now_anchor = datetime.now(timezone.utc).replace(tzinfo=None)
    if mode == "live":
        data_by_tf = feed.fetch_multi_timeframe(symbol, config.TIMEFRAMES, config.BARS_TO_FETCH)
    elif mode == "tradingview":
        data_by_tf = tradingview_feed.fetch_multi_timeframe(store, symbol, config.TIMEFRAMES)
        if not data_by_tf:
            raise RuntimeError(f"لا توجد بيانات TradingView كافية بعد للرمز {symbol}")
    else:
        data_by_tf = feed.generate_demo_multi_timeframe(
            config.TIMEFRAMES, config.BARS_TO_FETCH, seed_offset=hash(symbol) % 1000, end=now_anchor)

    correlations = None
    related = config.CORRELATION_SYMBOLS.get(symbol) if mode != "tradingview" else None
    if related:
        related_data = {}
        for rel_sym in related:
            try:
                if mode == "live":
                    related_data[rel_sym] = feed.fetch_ohlc(rel_sym, config.PRIMARY_TIMEFRAME, config.BARS_TO_FETCH)["close"]
                else:
                    related_data[rel_sym] = feed.generate_demo_ohlc(
                        config.BARS_TO_FETCH, seed=hash(rel_sym) % 1000, end=now_anchor)["close"]
            except Exception as e:
                logger.warning("correlation_fetch_failed", extra={"symbol": rel_sym, "error": str(e)})
                continue
        if related_data:
            base_close = data_by_tf[config.PRIMARY_TIMEFRAME]["close"]
            correlations = analyze_correlations(symbol, base_close, related_data)

    report = generate_trade_report(
        symbol=symbol, data_by_tf=data_by_tf,
        self_learning_engine=sl_engine, news_filter=None, correlations=correlations,
    )
    return report.to_dict()


def log_report_summary(report: dict):
    if not report["direction"]:
        logger.info("no_trade_signal", extra={"symbol": report["symbol"], "reasons": report["reasons_against"]})
        return
    logger.info("trade_report_generated", extra={
        "symbol": report["symbol"], "direction": report["direction"],
        "tradable": report["tradable"], "confluence_score": report["confluence_score"],
        "quality": report["quality"], "entry": report["entry"], "stop_loss": report["stop_loss"],
        "targets": report["targets"], "ml_win_probability": report["ml_win_probability"],
    })


def connect_live_feed():
    creds = get_mt5_credentials()
    if not all(creds.values()):
        logger.warning("mt5_credentials_incomplete_using_default_terminal_session")
        feed.connect()
        return
    login = int(creds["login"])
    feed.connect(login=login, password=creds["password"], server=creds["server"])
    logger.info("mt5_connected", extra={"server": creds["server"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "live", "tradingview"], default="demo")
    parser.add_argument("--interval", type=int, default=30, help="ثواني بين كل تحديث")
    parser.add_argument("--loop", action="store_true", help="تشغيل مستمر بدل مرة واحدة")
    args = parser.parse_args()

    store = get_store()

    if args.mode == "live":
        connect_live_feed()

    sl_engine = SelfLearningEngine(
        store=store,
        min_trades_before_training=config.MIN_TRADES_BEFORE_TRAINING,
        retrain_every=config.RETRAIN_EVERY_N_TRADES,
    )

    logger.info("engine_started", extra={"mode": args.mode, "symbols": config.SYMBOLS, "loop": args.loop})

    try:
        while True:
            for symbol in config.SYMBOLS:
                try:
                    report = run_once(symbol, args.mode, sl_engine, store)
                    store.save_signal(symbol, report)
                    log_report_summary(report)
                except Exception as e:
                    logger.error("symbol_analysis_failed", extra={"symbol": symbol, "error": str(e)}, exc_info=True)

            if sl_engine.should_retrain():
                result = sl_engine.train()
                logger.info("retrain_check_result", extra=result)

            if not args.loop:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("engine_stopped_by_user")
    finally:
        if args.mode == "live":
            feed.shutdown()


if __name__ == "__main__":
    main()
