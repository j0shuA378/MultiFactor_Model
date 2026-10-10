import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Add workspace directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data_loader import fetch_stock_data, get_preset_tickers
from core.indicators import add_all_indicators
from core.backtest_engine import BacktestEngine
from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.ml_predictor import MLPredictorStrategy
from strategies.turtle_grid import TurtleGridStrategy
from strategies.portfolio_allocator import blend_multi_strategy_portfolio

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
    "turtle": TurtleGridStrategy
}

# Dedicated Independent Page Routes
@app.route("/")
def index():
    return send_from_directory("static", "factor_model.html")

@app.route("/factor")
def page_factor():
    return send_from_directory("static", "factor_model.html")

@app.route("/ml")
def page_ml():
    return send_from_directory("static", "ml_model.html")

@app.route("/cta")
def page_cta():
    return send_from_directory("static", "cta_model.html")

@app.route("/portfolio")
def page_portfolio():
    return send_from_directory("static", "portfolio_model.html")

@app.route("/api/presets", methods=["GET"])
def api_presets():
    """Returns preset popular tickers"""
    return jsonify({"status": "success", "data": get_preset_tickers()})

@app.route("/api/stock/history", methods=["GET"])
def api_stock_history():
    """
    Returns historical candlestick OHLCV and indicator data
    Query params: ticker, period
    """
    ticker = request.args.get("ticker", "AAPL").upper().strip()
    period = request.args.get("period", "1y").lower().strip()

    try:
        df = fetch_stock_data(ticker, period)
        df_ind = add_all_indicators(df)
        
        # Prepare candlestick list
        candles = []
        for date, row in df_ind.iterrows():
            candles.append({
                "date": str(date),
                "open": round(float(row['Open']), 2),
                "high": round(float(row['High']), 2),
                "low": round(float(row['Low']), 2),
                "close": round(float(row['Close']), 2),
                "volume": int(row['Volume']),
                "sma_20": round(float(row['SMA_20']), 2) if 'SMA_20' in row and not row.isna()['SMA_20'] else None,
                "sma_50": round(float(row['SMA_50']), 2) if 'SMA_50' in row and not row.isna()['SMA_50'] else None,
                "rsi_14": round(float(row['RSI_14']), 2) if 'RSI_14' in row and not row.isna()['RSI_14'] else None,
                "bb_upper": round(float(row['BB_UPPER']), 2) if 'BB_UPPER' in row and not row.isna()['BB_UPPER'] else None,
                "bb_lower": round(float(row['BB_LOWER']), 2) if 'BB_LOWER' in row and not row.isna()['BB_LOWER'] else None,
                "macd_dif": round(float(row['MACD_DIF']), 2) if 'MACD_DIF' in row and not row.isna()['MACD_DIF'] else None,
                "macd_dea": round(float(row['MACD_DEA']), 2) if 'MACD_DEA' in row and not row.isna()['MACD_DEA'] else None,
                "macd_hist": round(float(row['MACD_HIST']), 2) if 'MACD_HIST' in row and not row.isna()['MACD_HIST'] else None,
            })

        latest_price = candles[-1]['close'] if candles else 0.0
        prev_price = candles[-2]['close'] if len(candles) > 1 else latest_price
        change_pct = round(((latest_price - prev_price) / prev_price) * 100.0, 2) if prev_price > 0 else 0.0

        return jsonify({
            "status": "success",
            "ticker": ticker,
            "period": period,
            "total_bars": len(candles),
            "latest_price": latest_price,
            "change_pct": change_pct,
            "candles": candles
        })
    except Exception as e:
        logger.error(f"Error fetching history for {ticker}: {e}")
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
    ticker = data.get("ticker", "AAPL").upper().strip()
    period = data.get("period", "1y").lower().strip()
    strategy_key = data.get("strategy", "momentum").lower().strip()
    capital = float(data.get("capital", 100000.0))
    commission_rate = float(data.get("commission_rate", 0.0005))
    slippage_rate = float(data.get("slippage_rate", 0.0005))
    stop_loss_pct = float(data["stop_loss_pct"]) / 100.0 if data.get("stop_loss_pct") else None
    take_profit_pct = float(data["take_profit_pct"]) / 100.0 if data.get("take_profit_pct") else None
    strategy_params = data.get("params", {})

    if strategy_key not in STRATEGY_MAP:
        return jsonify({"status": "error", "message": f"Unknown strategy: {strategy_key}"}), 400

    try:
        df = fetch_stock_data(ticker, period)
        if df.empty:
            return jsonify({"status": "error", "message": f"No data found for {ticker}"}), 404

        strat_class = STRATEGY_MAP[strategy_key]
        strat_instance = strat_class(params=strategy_params)

        signals, meta = strat_instance.generate_signals(df)
        pos_sizes = meta.get("position_sizes") if isinstance(meta, dict) else None

        engine = BacktestEngine(
            initial_capital=capital,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )

        result = engine.run(df, signals, position_sizes=pos_sizes)

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
            "signals": result["signals"]
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"AlphaQuant Web Platform running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
