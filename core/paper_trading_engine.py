import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from core.data_loader import fetch_stock_data, COMPANY_NAME_LOOKUP, sanitize_ticker
from core.metrics import compute_performance_metrics
from core.config_manager import load_config
from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.ml_predictor import MLPredictorStrategy
from strategies.turtle_grid import TurtleGridStrategy

logger = logging.getLogger("PaperTradingEngine")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PAPER_ACCOUNT_FILE = os.path.join(DATA_DIR, "paper_trading_account.json")
_PAPER_PRICE_CACHE: Dict[str, Tuple[datetime, float, float, str]] = {}

def is_us_market_open() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Checks whether the US Stock Market (NYSE/NASDAQ) is currently in regular trading hours.
    Regular hours: Mon-Fri, 09:30 to 16:00 US Eastern Time (America/New_York).
    Returns (is_open, status_text, detail_dict).
    """
    try:
        from zoneinfo import ZoneInfo
        now_et = datetime.now(ZoneInfo("America/New_York"))
        tz_abbr = now_et.tzname() or "ET"
    except Exception:
        now_utc = datetime.now(timezone.utc)
        month = now_utc.month
        # US Daylight Saving Time typically mid-March to early November (UTC-4), otherwise UTC-5
        offset = 4 if (3 <= month <= 11) else 5
        now_et = now_utc - timedelta(hours=offset)
        tz_abbr = "EDT" if offset == 4 else "EST"

    weekday = now_et.weekday()  # 0=Monday, ..., 4=Friday, 5=Saturday, 6=Sunday

    time_str = now_et.strftime("%H:%M:%S")
    date_str = now_et.strftime("%Y-%m-%d")

    # Weekend check
    if weekday >= 5:
        return False, "🔴 周末休市 (非美股交易日)", {
            "is_open": False,
            "session": "WEEKEND",
            "et_time": f"{date_str} {time_str} {tz_abbr}",
            "message": "美股周末休市，系统支持在回放与测试模式下进行全功能对盘模拟"
        }

    # Regular trading hours: 09:30:00 to 16:00:00
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    if market_open <= now_et <= market_close:
        return True, f"🟢 美股连续竞价交易中 (09:30 - 16:00 {tz_abbr})", {
            "is_open": True,
            "session": "REGULAR_MARKET",
            "et_time": f"{date_str} {time_str} {tz_abbr}",
            "message": "实时开盘对盘中，策略模型根据真实市价进行动态撮合"
        }
    elif now_et < market_open:
        return False, "🟡 盘前等待开盘 (Pre-Market)", {
            "is_open": False,
            "session": "PRE_MARKET",
            "et_time": f"{date_str} {time_str} {tz_abbr}",
            "message": "当前处于盘前时段，开盘前支持挂单与模拟撮合验证"
        }
    else:
        return False, "🔴 已收盘休市 (After-Hours / Closed)", {
            "is_open": False,
            "session": "CLOSED",
            "et_time": f"{date_str} {time_str} {tz_abbr}",
            "message": "美股今日常规时段已收盘，系统支持使用最新收盘价进行模拟对盘演算"
        }

class PaperTradingEngine:
    def __init__(self, storage_path: str = PAPER_ACCOUNT_FILE):
        self.storage_path = storage_path
        self.state = self.load_state()

    def get_default_state(self, initial_capital: float = 100000.0) -> Dict[str, Any]:
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "account": {
                "initial_capital": float(initial_capital),
                "cash": float(initial_capital),
                "total_equity": float(initial_capital),
                "positions_market_val": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "total_pnl": 0.0,
                "total_return_pct": 0.0,
                "daily_pnl": 0.0,
                "commission_paid": 0.0,
                "updated_at": now_iso
            },
            "config": {
                "strategy": "blend",           # 'momentum', 'ml', 'turtle', 'blend'
                "tickers": ["AAPL", "NVDA", "TSLA", "MSFT", "TSM"],
                "max_positions": 5,
                "position_size_pct": 0.20,      # 20% max per stock
                "commission_rate": 0.0005,      # 0.05%
                "slippage_rate": 0.0005,        # 0.05%
                "stop_loss_pct": 0.04,          # 4.0%
                "take_profit_pct": 0.08,        # 8.0%
                "auto_matching": False,
                "allow_after_hours": True
            },
            "positions": {},       # ticker -> position dict
            "orders": [],          # execution blotter list
            "trades_history": [],  # completed round-trip trades
            "equity_history": [    # timeline of portfolio value
                {
                    "timestamp": now_iso,
                    "date": now_iso.split(" ")[0],
                    "equity": float(initial_capital),
                    "cash": float(initial_capital),
                    "benchmark": float(initial_capital),
                    "drawdown_pct": 0.0
                }
            ],
            "signal_radar": []     # latest model evaluation signals
        }

    def load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "account" in data and "positions" in data:
                        return data
            except Exception as e:
                logger.error(f"Failed to read paper trading account state: {e}")
        state = self.get_default_state()
        self.save_state(state)
        return state

    def save_state(self, state: Optional[Dict[str, Any]] = None):
        if state is not None:
            self.state = state
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write paper trading account state: {e}")

    def reset_account(self, initial_capital: float = 100000.0) -> Dict[str, Any]:
        """Resets paper trading account back to clean state with given capital"""
        self.state = self.get_default_state(initial_capital=initial_capital)
        self.save_state()
        return self.get_summary()

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """Updates paper trading settings and persists"""
        self.state["config"].update(new_config)
        self.save_state()
        return self.state["config"]

    def get_latest_price(self, ticker: str) -> Tuple[float, float, str]:
        """
        Gets latest live price, previous close, and company name with 60s in-memory caching.
        Uses fast_info or latest bar from fetch_stock_data.
        """
        sym = sanitize_ticker(ticker)
        company_name = COMPANY_NAME_LOOKUP.get(sym, sym)
        now = datetime.now()

        # Check 60-second in-memory cache first to avoid request spamming
        if sym in _PAPER_PRICE_CACHE:
            cached_time, cached_price, cached_prev, cached_name = _PAPER_PRICE_CACHE[sym]
            if (now - cached_time).total_seconds() < 60:
                return cached_price, cached_prev, cached_name

        try:
            t = yf.Ticker(sym)
            fi = t.fast_info
            last = getattr(fi, 'last_price', None)
            prev = getattr(fi, 'previous_close', None)
            if last is not None and not np.isnan(last) and last > 0:
                p_close = float(prev) if (prev is not None and not np.isnan(prev) and prev > 0) else float(last)
                res = (float(last), p_close, company_name)
                _PAPER_PRICE_CACHE[sym] = (now, float(last), p_close, company_name)
                return res
        except Exception:
            pass

        # Fallback to local data
        df = fetch_stock_data(sym, period="1mo")
        if not df.empty:
            last = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2]) if len(df) > 1 else last
            _PAPER_PRICE_CACHE[sym] = (now, last, prev, company_name)
            return last, prev, company_name

        res = (100.0, 100.0, company_name)
        _PAPER_PRICE_CACHE[sym] = (now, 100.0, 100.0, company_name)
        return res

    def execute_order(
        self,
        ticker: str,
        action: str,            # 'BUY' or 'SELL'
        shares: int,
        price: Optional[float] = None,
        reason: str = "人工委托对盘",
        strategy: str = "Manual"
    ) -> Dict[str, Any]:
        """
        Executes a simulated matching order against market prices.
        Applies slippage and commission according to configuration.
        """
        sym = sanitize_ticker(ticker)
        action = action.upper().strip()
        if shares <= 0:
            return {"status": "error", "message": "委托股数必须大于 0"}

        curr_price, prev_close, comp_name = self.get_latest_price(sym)
        base_price = float(price) if (price and float(price) > 0) else curr_price

        cfg = self.state["config"]
        slip_rate = float(cfg.get("slippage_rate", 0.0005))
        comm_rate = float(cfg.get("commission_rate", 0.0005))

        # Slippage: BUY prices higher, SELL prices lower
        exec_price = base_price * (1.0 + slip_rate) if action == 'BUY' else base_price * (1.0 - slip_rate)
        exec_price = round(exec_price, 2)
        total_trade_value = round(shares * exec_price, 2)
        commission = round(max(1.0, total_trade_value * comm_rate), 2)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_id = f"ORD-{len(self.state['orders']) + 1001}"

        account = self.state["account"]
        positions = self.state["positions"]

        if action == 'BUY':
            total_cost = total_trade_value + commission
            if total_cost > account["cash"]:
                return {
                    "status": "error",
                    "message": f"可用资金不足: 需要 ${total_cost:,.2f}，当前可用 ${account['cash']:,.2f}"
                }

            account["cash"] = round(account["cash"] - total_cost, 2)
            account["commission_paid"] = round(account.get("commission_paid", 0.0) + commission, 2)

            # Update or create position
            if sym in positions:
                pos = positions[sym]
                old_shares = pos["shares"]
                old_cost = pos.get("avg_entry_price", pos.get("entry_price", exec_price)) * old_shares
                new_shares = old_shares + shares
                new_avg = round((old_cost + total_trade_value) / new_shares, 2)
                pos["shares"] = new_shares
                pos["avg_entry_price"] = new_avg
                pos["entry_price"] = new_avg
                pos["current_price"] = exec_price
                pos["company_name"] = pos.get("name", comp_name)
                pos["market_value"] = round(new_shares * exec_price, 2)
                pos["unrealized_pnl"] = round((exec_price - new_avg) * new_shares, 2)
                pos["unrealized_pnl_pct"] = round(((exec_price - new_avg) / new_avg) * 100.0, 2)
                pos["pnl_pct"] = pos["unrealized_pnl_pct"]
                pos["entry_comm"] = round(pos.get("entry_comm", 0.0) + commission, 2)
            else:
                sl_pct = float(cfg.get("stop_loss_pct", 0.04))
                tp_pct = float(cfg.get("take_profit_pct", 0.08))
                positions[sym] = {
                    "ticker": sym,
                    "name": comp_name,
                    "company_name": comp_name,
                    "shares": shares,
                    "avg_entry_price": exec_price,
                    "entry_price": exec_price,
                    "current_price": exec_price,
                    "market_value": total_trade_value,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "pnl_pct": 0.0,
                    "entry_comm": commission,
                    "entry_time": now_str,
                    "strategy": strategy,
                    "stop_loss_price": round(exec_price * (1.0 - sl_pct), 2),
                    "take_profit_price": round(exec_price * (1.0 + tp_pct), 2)
                }

            order_record = {
                "order_id": order_id,
                "timestamp": now_str,
                "ticker": sym,
                "name": comp_name,
                "action": "BUY",
                "shares": shares,
                "price": exec_price,
                "total_value": total_trade_value,
                "commission": commission,
                "status": "FILLED",
                "reason": reason,
                "strategy": strategy
            }
            self.state["orders"].insert(0, order_record)

        elif action == 'SELL':
            if sym not in positions or positions[sym]["shares"] < shares:
                avail_shares = positions.get(sym, {}).get("shares", 0)
                return {
                    "status": "error",
                    "message": f"可卖持仓不足: 申请卖出 {shares} 股，当前持仓仅 {avail_shares} 股"
                }

            pos = positions[sym]
            net_proceeds = round(total_trade_value - commission, 2)
            account["cash"] = round(account["cash"] + net_proceeds, 2)
            account["commission_paid"] = round(account.get("commission_paid", 0.0) + commission, 2)

            entry_p = pos["avg_entry_price"]
            cur_entry_comm = pos.get("entry_comm", 0.0)
            entry_comm_prop = round(cur_entry_comm * (shares / max(1, pos["shares"])), 2)
            pos["entry_comm"] = round(max(0.0, cur_entry_comm - entry_comm_prop), 2)
            trade_pnl = round((exec_price - entry_p) * shares - (entry_comm_prop + commission), 2)
            trade_pnl_pct = round(((exec_price - entry_p) / entry_p) * 100.0, 2)

            account["realized_pnl"] = round(account.get("realized_pnl", 0.0) + trade_pnl, 2)

            # Record closed trade
            trade_record = {
                "trade_id": len(self.state["trades_history"]) + 1,
                "ticker": sym,
                "name": comp_name,
                "entry_time": pos["entry_time"],
                "exit_time": now_str,
                "entry_price": entry_p,
                "exit_price": exec_price,
                "shares": shares,
                "pnl": trade_pnl,
                "pnl_pct": trade_pnl_pct,
                "commission": commission,
                "exit_reason": reason,
                "strategy": strategy
            }
            self.state["trades_history"].insert(0, trade_record)

            order_record = {
                "order_id": order_id,
                "timestamp": now_str,
                "ticker": sym,
                "name": comp_name,
                "action": "SELL",
                "shares": shares,
                "price": exec_price,
                "total_value": total_trade_value,
                "commission": commission,
                "status": "FILLED",
                "reason": reason,
                "strategy": strategy
            }
            self.state["orders"].insert(0, order_record)

            if shares == pos["shares"]:
                del positions[sym]
            else:
                pos["shares"] -= shares
                pos["market_value"] = round(pos["shares"] * exec_price, 2)
                pos["unrealized_pnl"] = round((exec_price - pos["avg_entry_price"]) * pos["shares"], 2)
                pos["unrealized_pnl_pct"] = round(((exec_price - pos["avg_entry_price"]) / pos["avg_entry_price"]) * 100.0, 2)

        # Mark to market and recalculate account metrics
        self.mark_to_market()
        self.save_state()

        return {
            "status": "success",
            "message": f"成功撮合 {action} {shares} 股 {sym}，成交价 ${exec_price:.2f}",
            "order": order_record,
            "account": self.state["account"]
        }

    def close_position(self, ticker: str, reason: str = "市价平仓") -> Dict[str, Any]:
        """
        Closes all shares of an active position for a given ticker.
        """
        sym = sanitize_ticker(ticker)
        positions = self.state.get("positions", {})
        if sym not in positions:
            return {"status": "error", "message": f"未持有 {sym} 的头寸"}

        pos = positions[sym]
        shares_to_sell = pos["shares"]
        strat = pos.get("strategy", "Manual")
        res = self.execute_order(
            ticker=sym,
            action="SELL",
            shares=shares_to_sell,
            reason=reason,
            strategy=strat
        )
        if res.get("status") == "success":
            closed_trade = self.state["trades_history"][0] if self.state["trades_history"] else {}
            res["closed_trade"] = closed_trade
        return res

    def mark_to_market(self):
        """Refreshes all open positions with latest prices and recalculates equity"""
        account = self.state["account"]
        positions = self.state["positions"]

        total_mv = 0.0
        total_unrealized = 0.0

        for sym, pos in list(positions.items()):
            curr_p, _, _ = self.get_latest_price(sym)
            shares = pos["shares"]
            entry_p = pos.get("avg_entry_price", pos.get("entry_price", curr_p))
            mv = round(shares * curr_p, 2)
            u_pnl = round((curr_p - entry_p) * shares, 2)
            u_pct = round(((curr_p - entry_p) / entry_p) * 100.0, 2) if entry_p > 0 else 0.0

            pos["current_price"] = curr_p
            pos["market_value"] = mv
            pos["unrealized_pnl"] = u_pnl
            pos["unrealized_pnl_pct"] = u_pct
            pos["pnl_pct"] = u_pct
            pos["entry_price"] = entry_p
            pos["company_name"] = pos.get("name", sym)

            total_mv += mv
            total_unrealized += u_pnl

        account["positions_market_val"] = round(total_mv, 2)
        account["unrealized_pnl"] = round(total_unrealized, 2)
        account["total_equity"] = round(account["cash"] + total_mv, 2)
        
        init_cap = account.get("initial_capital", 100000.0)
        tot_ret = round(((account["total_equity"] - init_cap) / init_cap) * 100.0, 2)
        account["total_return_pct"] = tot_ret
        account["total_pnl"] = round(account["total_equity"] - init_cap, 2)
        account["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Append or update equity history point
        self.record_equity_point()

    def record_equity_point(self):
        now_dt = datetime.now()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        account = self.state["account"]
        eq_hist = self.state.get("equity_history", [])

        # Avoid redundant duplicate timestamps within same 10 seconds
        if eq_hist:
            last_pt = eq_hist[-1]
            try:
                last_dt = datetime.strptime(last_pt["timestamp"], "%Y-%m-%d %H:%M:%S")
                if (now_dt - last_dt).total_seconds() < 10:
                    last_pt["equity"] = account["total_equity"]
                    last_pt["cash"] = account["cash"]
                    return
            except Exception:
                pass

        # Calculate rolling drawdown
        eq_vals = [pt["equity"] for pt in eq_hist] + [account["total_equity"]]
        peak = max(eq_vals) if eq_vals else account["total_equity"]
        curr_dd = round(((account["total_equity"] - peak) / peak) * 100.0, 2) if peak > 0 else 0.0

        # Benchmark SPY value
        spy_price, _, _ = self.get_latest_price("SPY")
        init_cap = account.get("initial_capital", 100000.0)
        first_spy = eq_hist[0].get("spy_ref_price") if eq_hist else None
        if not first_spy or first_spy <= 0:
            first_spy = spy_price
            if eq_hist:
                eq_hist[0]["spy_ref_price"] = first_spy
        bench_val = round(init_cap * (spy_price / max(first_spy, 1e-4)), 2)

        eq_hist.append({
            "timestamp": now_str,
            "date": now_str.split(" ")[0],
            "equity": account["total_equity"],
            "cash": account["cash"],
            "benchmark": bench_val,
            "spy_ref_price": first_spy,
            "drawdown_pct": abs(curr_dd)
        })

        # Cap history to 500 points for smooth charting
        if len(eq_hist) > 500:
            self.state["equity_history"] = eq_hist[-500:]

    def step_market_matching(self, force_step: bool = False) -> Dict[str, Any]:
        """
        Core automated simulation matching step:
        1. Checks US market open status (or checks allow_after_hours setting).
        2. Inspects all open positions for Take Profit / Stop Loss triggers.
        3. Runs configured quantitative model on universe tickers.
        4. Matches BUY orders if buy conditions met and capacity available.
        5. Updates equity, radar signals, and persists state.
        """
        is_open, open_text, open_detail = is_us_market_open()
        cfg = self.state["config"]

        if not is_open and not cfg.get("allow_after_hours", True) and not force_step:
            return {
                "status": "market_closed",
                "message": f"当前美股休市: {open_text}。如需测试对盘，请开启'允许非交易时段模拟'选项或点击强制步进。",
                "is_open": False
            }

        tickers = cfg.get("tickers", ["AAPL", "NVDA", "TSLA", "MSFT", "TSM"])
        strategy_key = cfg.get("strategy", "blend")
        max_positions = int(cfg.get("max_positions", 5))
        pos_size_pct = float(cfg.get("position_size_pct", 0.20))
        stop_loss_pct = float(cfg.get("stop_loss_pct", 0.04))
        take_profit_pct = float(cfg.get("take_profit_pct", 0.08))

        matched_orders = []
        radar_signals = []

        # 1. First Pass: Monitor Existing Positions for Risk Control (Stop Loss / Take Profit)
        for sym, pos in list(self.state["positions"].items()):
            curr_p, _, comp_name = self.get_latest_price(sym)
            entry_p = pos["avg_entry_price"]
            pnl_pct = (curr_p - entry_p) / entry_p

            sl_price = pos.get("stop_loss_price") or (entry_p * (1.0 - stop_loss_pct))
            tp_price = pos.get("take_profit_price") or (entry_p * (1.0 + take_profit_pct))

            exit_reason = None
            if curr_p <= sl_price or pnl_pct <= -stop_loss_pct:
                exit_reason = f"触发动态止损保护 (-{abs(pnl_pct)*100:.1f}%)"
            elif curr_p >= tp_price or pnl_pct >= take_profit_pct:
                exit_reason = f"触发目标止盈离场 (+{pnl_pct*100:.1f}%)"

            if exit_reason:
                res = self.execute_order(
                    ticker=sym,
                    action='SELL',
                    shares=pos["shares"],
                    price=curr_p,
                    reason=exit_reason,
                    strategy=pos.get("strategy", strategy_key)
                )
                if res.get("status") == "success":
                    matched_orders.append(res["order"])

        # 2. Second Pass: Evaluate Model Alpha on Universe Tickers
        for sym in tickers:
            try:
                df = fetch_stock_data(sym, period="1y")
                if df.empty or len(df) < 30:
                    continue

                curr_p, _, comp_name = self.get_latest_price(sym)
                is_currently_held = sym in self.state["positions"]

                # Run strategy
                sig_val = 0
                confidence = 78
                expected_buy = curr_p
                decision_state = "WATCH"
                desc = "无明显交易信号"

                if strategy_key == "ml":
                    strat = MLPredictorStrategy()
                    sigs, meta = strat.generate_signals(df)
                    sig_val = int(sigs.iloc[-1]) if len(sigs) > 0 else 0
                    probs = meta.get("prediction_probs", {})
                    if probs:
                        last_p = list(probs.values())[-1]
                        confidence = int(last_p * 100.0) if isinstance(last_p, (int, float)) else 80
                    strat_name = "ML AI预测"
                elif strategy_key == "turtle":
                    strat = TurtleGridStrategy()
                    sigs, meta = strat.generate_signals(df)
                    sig_val = int(sigs.iloc[-1]) if len(sigs) > 0 else 0
                    strat_name = "CTA通道突破"
                else:
                    # Default: Multi-Factor Momentum
                    strat = MultiFactorMomentumStrategy()
                    sigs, meta = strat.generate_signals(df)
                    sig_val = int(sigs.iloc[-1]) if len(sigs) > 0 else 0
                    strat_name = "多因子Alpha"

                # Check action trigger
                if is_currently_held:
                    decision_state = "HOLDING"
                    desc = f"持仓中 (现价 ${curr_p:.2f})"
                    if sig_val < 0:
                        # Model generated sell signal
                        res = self.execute_order(
                            ticker=sym,
                            action='SELL',
                            shares=self.state["positions"][sym]["shares"],
                            price=curr_p,
                            reason=f"{strat_name} 触发卖出离场信号",
                            strategy=strat_name
                        )
                        if res.get("status") == "success":
                            matched_orders.append(res["order"])
                            decision_state = "EXIT_MATCHED"
                            desc = f"已撮合平仓卖出 (${curr_p:.2f})"
                else:
                    if sig_val > 0:
                        decision_state = "BUY_SIGNAL"
                        desc = f"{strat_name} 达成买入条件"

                        # Check capacity to open new position
                        active_count = len(self.state["positions"])
                        if active_count < max_positions:
                            avail_cash = self.state["account"]["cash"]
                            target_alloc = self.state["account"]["total_equity"] * pos_size_pct
                            deploy_cash = min(avail_cash * 0.95, target_alloc)

                            buy_shares = int(deploy_cash / max(1.0, curr_p))
                            if buy_shares > 0:
                                res = self.execute_order(
                                    ticker=sym,
                                    action='BUY',
                                    shares=buy_shares,
                                    price=curr_p,
                                    reason=f"{strat_name} 共振突破自动撮合买入",
                                    strategy=strat_name
                                )
                                if res.get("status") == "success":
                                    matched_orders.append(res["order"])
                                    decision_state = "BOUGHT"
                                    desc = f"已撮合成交建仓 {buy_shares} 股"
                            else:
                                desc = "触发买点，但账户可用现金不足"
                        else:
                            desc = f"触发买点，但持仓数已达上限 ({max_positions})"
                    else:
                        decision_state = "WATCH"
                        desc = "均线通道内震荡，逢低观望"

                radar_signals.append({
                    "ticker": sym,
                    "name": comp_name,
                    "price": curr_p,
                    "signal": sig_val,
                    "state": decision_state,
                    "strategy": strat_name,
                    "confidence": confidence,
                    "status_desc": desc,
                    "updated_at": datetime.now().strftime("%H:%M:%S")
                })

            except Exception as e:
                logger.warning(f"Error stepping ticker {sym}: {e}")

        self.state["signal_radar"] = radar_signals
        self.mark_to_market()
        self.save_state()

        return {
            "status": "success",
            "market_open": is_open,
            "session_info": open_detail,
            "matched_orders_count": len(matched_orders),
            "matched_orders": matched_orders,
            "radar_signals": radar_signals,
            "account": self.state["account"]
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns comprehensive account summary, KPIs, and blotters"""
        self.mark_to_market()
        account = self.state["account"]
        trades = self.state["trades_history"]
        is_open, open_text, open_detail = is_us_market_open()

        # Trade performance metrics
        tot_trades = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]

        win_rate = round(len(wins) / tot_trades * 100.0, 1) if tot_trades > 0 else 0.0
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        # Drawdown and returns from equity history
        eq_hist = self.state.get("equity_history", [])
        peak_eq = max([pt["equity"] for pt in eq_hist]) if eq_hist else account["total_equity"]
        curr_dd = round(((account["total_equity"] - peak_eq) / peak_eq) * 100.0, 2) if peak_eq > 0 else 0.0
        max_dd = max([pt.get("drawdown_pct", 0.0) for pt in eq_hist]) if eq_hist else 0.0

        return {
            "status": "success",
            "market_status": {
                "is_open": is_open,
                "status_text": open_text,
                "session": open_detail.get("session"),
                "et_time": open_detail.get("et_time"),
                "message": open_detail.get("message")
            },
            "account": account,
            "config": self.state["config"],
            "kpis": {
                "total_equity": account["total_equity"],
                "cash": account["cash"],
                "market_value": account["positions_market_val"],
                "total_return_pct": account["total_return_pct"],
                "total_pnl": account["total_pnl"],
                "unrealized_pnl": account["unrealized_pnl"],
                "realized_pnl": account["realized_pnl"],
                "win_rate_pct": win_rate,
                "profit_factor": profit_factor,
                "total_trades": tot_trades,
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "max_drawdown_pct": max_dd,
                "current_drawdown_pct": abs(curr_dd)
            },
            "positions": list(self.state["positions"].values()),
            "orders": self.state["orders"][:50],           # last 50 orders
            "trades_history": self.state["trades_history"][:50],
            "equity_history": self.state["equity_history"][-120:], # last 120 timeline points
            "signal_radar": self.state.get("signal_radar", [])
        }

# Global singleton engine instance
paper_engine = PaperTradingEngine()
