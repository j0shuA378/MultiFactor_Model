import os
import sys
import math
import logging
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Add workspace directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import (
    fetch_stock_data,
    fetch_realtime_quote,
    get_preset_tickers,
    search_yahoo_tickers,
    sanitize_ticker,
    get_ticker_metadata,
    fetch_stock_fundamentals,
    get_screener_catalog
)
from core.config_manager import load_config, save_config, apply_preset, reset_to_defaults, INSTITUTIONAL_PRESETS
from core.indicators import add_all_indicators
from core.backtest_engine import BacktestEngine
from core.prediction_engine import generate_trade_prediction
from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.ml_predictor import MLPredictorStrategy
from strategies.turtle_grid import TurtleGridStrategy
from strategies.chan_strategy import ChanTheoryStrategy
from strategies.portfolio_allocator import blend_multi_strategy_portfolio
from core.paper_trading_engine import paper_engine, is_us_market_open

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QuantServer")

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

def sanitize_json(obj):
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_json(x) for x in obj]
    elif hasattr(obj, 'to_dict') and hasattr(obj, 'iloc'):  # pandas Series
        return {str(k): sanitize_json(v) for k, v in obj.iloc[-30:].items()}
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif isinstance(obj, float):
        import math
        return None if math.isnan(obj) else round(obj, 4)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj

STRATEGY_MAP = {
    "momentum": MultiFactorMomentumStrategy,
    "ml": MLPredictorStrategy,
    "turtle": TurtleGridStrategy,
    "chan": ChanTheoryStrategy
}

# Dedicated Independent Page Routes
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/factor")
@app.route("/static/factor_model.html")
def page_factor():
    return send_from_directory("static", "index.html")

@app.route("/ml")
@app.route("/static/ml_model.html")
def page_ml():
    return send_from_directory("static", "index.html")

@app.route("/cta")
@app.route("/static/cta_model.html")
def page_cta():
    return send_from_directory("static", "index.html")

@app.route("/portfolio")
def page_portfolio():
    return send_from_directory("static", "index.html")

@app.route("/settings")
@app.route("/settings.html")
def page_settings():
    return send_from_directory("static", "settings.html")

@app.route("/paper")
@app.route("/paper_trading.html")
def page_paper():
    return send_from_directory("static", "paper_trading.html")

@app.route("/api/presets", methods=["GET"])
def api_presets():
    """Returns preset popular tickers"""
    return jsonify({"status": "success", "data": get_preset_tickers()})

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Returns current saved configuration along with available institutional presets"""
    cfg = load_config()
    return jsonify({
        "status": "success",
        "data": cfg,
        "presets": INSTITUTIONAL_PRESETS
    })

@app.route("/api/config", methods=["POST"])
def api_save_config():
    """Saves updated user configuration to backend persistence"""
    data = request.get_json() or {}
    updated = save_config(data)
    return jsonify({
        "status": "success",
        "message": "Configuration saved successfully",
        "data": updated
    })

@app.route("/api/config/presets", methods=["GET"])
def api_get_presets():
    """Returns list of institutional presets"""
    return jsonify({
        "status": "success",
        "data": INSTITUTIONAL_PRESETS
    })

@app.route("/api/config/preset/apply", methods=["POST"])
def api_apply_preset():
    """Applies an institutional preset to the configuration"""
    data = request.get_json() or {}
    preset_id = data.get("preset_id")
    if not preset_id:
        return jsonify({"status": "error", "message": "Missing preset_id"}), 400
    try:
        updated = apply_preset(preset_id)
        return jsonify({
            "status": "success",
            "message": f"Preset '{preset_id}' applied successfully",
            "data": updated
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/config/reset", methods=["POST"])
def api_reset_config():
    """Resets configuration to factory defaults"""
    cfg = reset_to_defaults()
    return jsonify({
        "status": "success",
        "message": "Configuration reset to factory defaults",
        "data": cfg
    })

@app.route("/api/search", methods=["GET"])
def api_search():
    """
    Search Yahoo Finance for tickers/companies matching query.
    Returns max 5 candidate items with real-time price and percentage change.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"status": "success", "data": []})
    
    try:
        results = search_yahoo_tickers(q, max_results=5)
        return jsonify({"status": "success", "query": q, "data": results})
    except Exception as e:
        logger.error(f"Search API error for '{q}': {e}")
        return jsonify({"status": "error", "message": str(e), "data": []})

@app.route("/api/stock/history", methods=["GET"])
def api_stock_history():
    """
    Returns historical candlestick OHLCV and indicator data
    Query params: ticker, period
    """
    ticker = sanitize_ticker(request.args.get("ticker", "AAPL"))
    period = request.args.get("period", "1y").lower().strip()

    try:
        df = fetch_stock_data(ticker, period)
        df_ind = add_all_indicators(df)
        
        # Prepare candlestick list with high-performance itertuples
        candles = []
        def _val(x):
            return round(float(x), 2) if (x is not None and not np.isnan(x)) else None

        for row in df_ind.itertuples():

            candles.append({
                "date": str(row.Index),
                "open": round(float(row.Open), 2),
                "high": round(float(row.High), 2),
                "low": round(float(row.Low), 2),
                "close": round(float(row.Close), 2),
                "volume": int(row.Volume),
                "sma_20": _val(getattr(row, 'SMA_20', None)),
                "sma_50": _val(getattr(row, 'SMA_50', None)),
                "rsi_14": _val(getattr(row, 'RSI_14', None)),
                "bb_upper": _val(getattr(row, 'BB_UPPER', None)),
                "bb_lower": _val(getattr(row, 'BB_LOWER', None)),
                "macd_dif": _val(getattr(row, 'MACD_DIF', None)),
                "macd_dea": _val(getattr(row, 'MACD_DEA', None)),
                "macd_hist": _val(getattr(row, 'MACD_HIST', None)),
            })

        latest_price = candles[-1]['close'] if candles else 0.0
        prev_price = candles[-2]['close'] if len(candles) > 1 else latest_price
        change_pct = round(((latest_price - prev_price) / prev_price) * 100.0, 2) if prev_price > 0 else 0.0

        is_open, status_text, detail = is_us_market_open()
        meta = get_ticker_metadata(ticker)

        return jsonify({
            "status": "success",
            "ticker": ticker,
            "name": meta.get("name"),
            "exchange": meta.get("exchange"),
            "type": meta.get("type"),
            "currency": meta.get("currency"),
            "period": period,
            "total_bars": len(candles),
            "latest_price": latest_price,
            "change_pct": change_pct,
            "is_market_open": is_open,
            "market_status_text": status_text,
            "market_session": detail.get("session", "CLOSED"),
            "candles": candles
        })
    except Exception as e:
        logger.error(f"Error fetching history for {ticker}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/stock/quote", methods=["GET"])
def api_stock_quote():
    """
    Returns real-time live market quote directly from finance.yahoo.com
    Query params: ticker
    """
    ticker = sanitize_ticker(request.args.get("ticker", "AAPL"))
    try:
        quote = fetch_realtime_quote(ticker)
        is_open, status_text, detail = is_us_market_open()
        quote["is_market_open"] = is_open
        quote["market_status_text"] = status_text
        quote["market_session"] = detail.get("session", "CLOSED")
        return jsonify(quote)
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}")
        return jsonify({"status": "error", "message": str(e), "ticker": ticker}), 500

@app.route("/api/stock/fundamentals", methods=["GET"])
def api_stock_fundamentals():
    """
    Step 2 Endpoint:
    Returns complete institutional fundamentals, financials, valuation multiples,
    Wall Street analyst target price consensus, and dividend schedules.
    Query params: ticker
    """
    ticker = sanitize_ticker(request.args.get("ticker", "AAPL"))
    try:
        data = fetch_stock_fundamentals(ticker)
        return jsonify(sanitize_json(data))
    except Exception as e:
        logger.error(f"Error in api_stock_fundamentals for {ticker}: {e}")
        return jsonify({"status": "error", "message": str(e), "ticker": ticker}), 500

@app.route("/api/screener", methods=["GET"])
def api_screener():
    """
    Step 1 Endpoint:
    Returns curated multi-market stock universe for 选股大厅 (Screener).
    Query params: category (all, us_tech, etf_gold, china_hk, a_shares, high_dividend)
    """
    category = request.args.get("category", "all").strip().lower()
    try:
        catalog = get_screener_catalog(category)
        return jsonify({
            "status": "success",
            "category": category,
            "count": len(catalog),
            "stocks": catalog
        })
    except Exception as e:
        logger.error(f"Error in api_screener: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/chan/analysis", methods=["GET"])
def api_chan_analysis():
    """
    Returns full Chan Theory morphology and dynamics analysis:
    merged bars, fractals, bis, zhongshus, and buy/sell points.
    Query params: ticker, period
    """
    ticker = sanitize_ticker(request.args.get("ticker", "AAPL"))
    period = request.args.get("period", "1y").lower().strip()
    try:
        df = fetch_stock_data(ticker, period)
        from core.chan_theory import run_chan_analysis
        result = run_chan_analysis(df)
        active_zs = result.get("active_zhongshu")
        return jsonify({
            "status": "success",
            "ticker": ticker,
            "period": period,
            "merged_bars": result.get("merged_bars_count", 0),
            "fractals": result.get("fractals_count", 0),
            "bis": result.get("bis_count", 0),
            "zhongshus": result.get("zhongshus_count", 0),
            "tags": result.get("tags", {}),
            "active_zhongshu": {
                "zg": active_zs.zg,
                "zd": active_zs.zd,
                "gg": active_zs.gg,
                "dd": active_zs.dd,
                "bi_count": active_zs.bi_count
            } if active_zs else None
        })
    except Exception as e:
        logger.error(f"Error in Chan analysis for {ticker}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """
    Executes backtest for a chosen strategy
    Body JSON:
    {
        "ticker": "AAPL",
        "period": "1y",
        "strategy": "momentum" | "ml" | "turtle",
        "capital": 100000,
        "commission_rate": 0.0005,
        "slippage_rate": 0.0005,
        "params": {...}
    }
    """
    data = request.get_json() or {}
    ticker = sanitize_ticker(data.get("ticker", "AAPL"))
    period = data.get("period", "1y").lower().strip()
    strategy_key = data.get("strategy", "momentum").lower().strip()
    
    if strategy_key not in STRATEGY_MAP:
        return jsonify({"status": "error", "message": f"Unknown strategy: {strategy_key}"}), 400

    cfg = load_config()
    account_cfg = cfg.get("account", {})
    saved_strat_cfg = cfg.get(strategy_key, {})

    def _normalize_fee(val, fallback=0.05):
        if val is not None and str(val).strip() != "":
            try:
                v = float(val)
                return v / 100.0 if v >= 0.01 else v
            except (ValueError, TypeError):
                pass
        try:
            fb = float(fallback)
            return fb / 100.0 if fb >= 0.01 else fb
        except (ValueError, TypeError):
            return 0.0005

    capital = float(data.get("capital", account_cfg.get("initial_capital", 100000.0)))
    commission_rate = _normalize_fee(data.get("commission_rate"), account_cfg.get("commission_rate", 0.05))
    slippage_rate = _normalize_fee(data.get("slippage_rate"), account_cfg.get("slippage_rate", 0.05))
    
    def _parse_pct(val, fallback=None):
        if val is not None and str(val).strip() != "":
            try:
                v = float(val)
                if v > 0:
                    return v / 100.0
            except (ValueError, TypeError):
                pass
        if fallback is not None and str(fallback).strip() != "":
            try:
                fb = float(fallback)
                if fb > 0:
                    return fb / 100.0
            except (ValueError, TypeError):
                pass
        return None

    stop_loss_pct = _parse_pct(data.get("stop_loss_pct"), account_cfg.get("stop_loss_pct"))
    take_profit_pct = _parse_pct(data.get("take_profit_pct"), account_cfg.get("take_profit_pct"))
    
    strategy_params = dict(saved_strat_cfg)
    strategy_params.update(data.get("params", {}))

    try:
        df = fetch_stock_data(ticker, period)
        if df.empty:
            return jsonify({"status": "error", "message": f"No data found for {ticker}"}), 404

        strat_class = STRATEGY_MAP[strategy_key]
        strat_instance = strat_class(params=strategy_params)

        signals, meta = strat_instance.generate_signals(df)
        pos_sizes = meta.get("position_sizes") if isinstance(meta, dict) else None

        exec_mode = str(data.get("execution_mode", "next_open")).lower().strip()
        if exec_mode not in ["next_open", "same_close"]:
            exec_mode = "next_open"

        engine = BacktestEngine(
            initial_capital=capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            execution_mode=exec_mode,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )

        result = engine.run(df, signals, position_sizes=pos_sizes)

        # Compute forward trade prediction, expected buy point, target profit, and stop loss
        trade_prediction = generate_trade_prediction(
            df=df,
            signals=signals,
            trades=result["trades"],
            meta=meta,
            strategy_key=strategy_key,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct
        )

        response_payload = {
            "status": "success",
            "ticker": ticker,
            "period": period,
            "strategy": strategy_key,
            "strategy_name": strat_instance.name,
            "meta": meta,
            "metrics": result["metrics"],
            "equity_curve": result["equity_curve"],
            "trades": result["trades"],
            "signals": result["signals"],
            "trade_prediction": trade_prediction
        }
        return jsonify(sanitize_json(response_payload))
    except Exception as e:
        logger.error(f"Error during backtest: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/compare", methods=["POST"])
def api_compare():
    """
    Runs all 3 strategies on the same ticker and returns side-by-side comparison
    """
    data = request.get_json() or {}
    ticker = data.get("ticker", "AAPL").upper().strip()
    period = data.get("period", "1y").lower().strip()
    capital = float(data.get("capital", 100000.0))

    try:
        df = fetch_stock_data(ticker, period)
        if df.empty:
            return jsonify({"status": "error", "message": f"No data found for {ticker}"}), 404

        engine = BacktestEngine(initial_capital=capital)
        comparison_results = []

        for key, strat_class in STRATEGY_MAP.items():
            strat = strat_class()
            signals, meta = strat.generate_signals(df)
            pos_sizes = meta.get("position_sizes") if isinstance(meta, dict) else None
            res = engine.run(df, signals, position_sizes=pos_sizes)
            comparison_results.append({
                "strategy_key": key,
                "strategy_name": strat.name,
                "metrics": res["metrics"],
                "trades_count": len(res["trades"]),
                "equity_curve": [
                    {"date": item["date"], "equity": item["equity"], "benchmark": item["benchmark"]}
                    for item in res["equity_curve"]
                ]
            })

        response_payload = {
            "status": "success",
            "ticker": ticker,
            "period": period,
            "results": comparison_results
        }
        return jsonify(sanitize_json(response_payload))
    except Exception as e:
        logger.error(f"Error comparing strategies: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portfolio/blend", methods=["POST"])
def api_portfolio_blend():
    """
    Simulates an institutional multi-strategy portfolio with custom factor/strategy weights
    Body JSON:
    {
        "ticker": "AAPL",
        "period": "1y",
        "capital": 100000,
        "weights": {"momentum": 0.4, "ml": 0.4, "turtle": 0.2}
    }
    """
    data = request.get_json() or {}
    ticker = data.get("ticker", "AAPL").upper().strip()
    period = data.get("period", "1y").lower().strip()
    capital = float(data.get("capital", 100000.0))
    weights = data.get("weights", {"momentum": 0.4, "ml": 0.4, "turtle": 0.2})

    try:
        df = fetch_stock_data(ticker, period)
        if df.empty:
            return jsonify({"status": "error", "message": f"No data found for {ticker}"}), 404

        engine = BacktestEngine(initial_capital=capital)
        results_map = {}

        for key, strat_class in STRATEGY_MAP.items():
            strat = strat_class()
            signals, meta = strat.generate_signals(df)
            pos_sizes = meta.get("position_sizes") if isinstance(meta, dict) else None
            res = engine.run(df, signals, position_sizes=pos_sizes)
            res["strategy_name"] = strat.name
            results_map[key] = res

        blended_result = blend_multi_strategy_portfolio(results_map, weights, initial_capital=capital)

        payload = {
            "status": "success",
            "ticker": ticker,
            "period": period,
            "individual_strategies": {
                k: {
                    "name": v["strategy_name"],
                    "metrics": v["metrics"],
                    "trades_count": len(v["trades"])
                }
                for k, v in results_map.items()
            },
            "blended": blended_result
        }
        return jsonify(sanitize_json(payload))
    except Exception as e:
        logger.error(f"Error blending portfolio: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# =========================================================================
# Paper Trading (模拟对盘交易与模型性能记录) API Endpoints
# =========================================================================

@app.route("/api/paper/status", methods=["GET"])
def api_paper_status():
    """
    Returns full paper trading account summary, live PnL, positions,
    execution blotter, round-trip trades, equity history, and market session info.
    """
    try:
        summary = paper_engine.get_summary()
        return jsonify(sanitize_json(summary))
    except Exception as e:
        logger.error(f"Error getting paper trading summary: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/step", methods=["POST"])
def api_paper_step():
    """
    Executes one matching cycle:
    1. Checks if regular market hours or if force_step is requested.
    2. Runs quantitative model signals across configured stock universe.
    3. Triggers simulated order matching, risk checks (stop loss/take profit), and updates ledger.
    """
    try:
        data = request.get_json() or {}
        force_step = bool(data.get("force_step", False))
        result = paper_engine.step_market_matching(force_step=force_step)
        return jsonify(sanitize_json(result))
    except Exception as e:
        logger.error(f"Error stepping paper trading matching: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/order", methods=["POST"])
def api_paper_order():
    """
    Executes a manual or algorithmic paper order.
    Payload: { "ticker": "AAPL", "action": "BUY"|"SELL", "shares": 10, "price": Optional[float], "reason": str }
    """
    try:
        data = request.get_json() or {}
        ticker = data.get("ticker", "").upper().strip()
        action = data.get("action", "BUY").upper().strip()
        shares = int(data.get("shares", 0))
        price = data.get("price")
        price = float(price) if price is not None and str(price).strip() != "" else None
        reason = data.get("reason", "交易员人工委托")
        strategy = data.get("strategy", "Manual")

        if not ticker or shares <= 0:
            return jsonify({"status": "error", "message": "标的代码不能为空且委托股数必须大于0"}), 400

        res = paper_engine.execute_order(
            ticker=ticker,
            action=action,
            shares=shares,
            price=price,
            reason=reason,
            strategy=strategy
        )
        return jsonify(sanitize_json(res))
    except Exception as e:
        logger.error(f"Error executing paper order: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/close_position", methods=["POST"])
def api_paper_close_position():
    """
    Closes an active position for a given symbol at market price.
    Payload: { "ticker": "AAPL", "reason": Optional[str] }
    """
    try:
        data = request.get_json() or {}
        ticker = data.get("ticker", "").upper().strip()
        reason = data.get("reason", "一键市价平仓")
        if not ticker:
            return jsonify({"status": "error", "message": "标的代码不能为空"}), 400

        res = paper_engine.close_position(ticker=ticker, reason=reason)
        return jsonify(sanitize_json(res))
    except Exception as e:
        logger.error(f"Error closing paper position: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/reset", methods=["POST"])
def api_paper_reset():
    """
    Resets the paper trading account, wiping existing positions and blotters,
    and restoring initial simulated capital.
    Payload: { "initial_capital": 100000.0 }
    """
    try:
        data = request.get_json() or {}
        initial_capital = float(data.get("initial_capital", 100000.0))
        res = paper_engine.reset_account(initial_capital=initial_capital)
        return jsonify(sanitize_json(res))
    except Exception as e:
        logger.error(f"Error resetting paper trading account: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/config", methods=["POST"])
def api_paper_config():
    """
    Updates paper trading engine parameters (universe, strategy, risk controls, auto matching).
    """
    try:
        data = request.get_json() or {}
        updated_cfg = paper_engine.update_config(data)
        return jsonify({"status": "success", "config": sanitize_json(updated_cfg)})
    except Exception as e:
        logger.error(f"Error updating paper trading config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/paper/market_hours", methods=["GET"])
def api_paper_market_hours():
    """
    Returns US stock market open/closed status with Eastern Time details.
    """
    try:
        is_open, status_text, detail = is_us_market_open()
        return jsonify({
            "status": "success",
            "is_open": is_open,
            "status_text": status_text,
            "detail": detail
        })
    except Exception as e:
        logger.error(f"Error getting market hours: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"AlphaQuant Web Platform running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
