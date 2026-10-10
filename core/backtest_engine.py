import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from core.metrics import compute_performance_metrics, calculate_drawdown_series

class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0005,  # 0.05% commission
        min_commission: float = 1.0,      # $1.00 minimum
        slippage_rate: float = 0.0005,    # 0.05% slippage
        position_size_pct: float = 0.95,  # 95% max capital deployed
        stop_loss_pct: Optional[float] = None,   # e.g. 0.05 for 5% stop loss
        take_profit_pct: Optional[float] = None  # e.g. 0.15 for 15% take profit
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_rate = slippage_rate
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def calculate_commission(self, trade_value: float) -> float:
        return max(self.min_commission, trade_value * self.commission_rate)

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        position_sizes: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Executes backtest step-by-step across the price timeline.
        df: OHLCV DataFrame indexed by Date
        signals: Series of integer signals (-1, 0, 1) indexed by Date
        position_sizes: Optional fraction (0.0 to 1.0) or custom share sizes
        """
        dates = df.index.tolist()
        if not dates or len(dates) == 0:
            return {
                "metrics": {},
                "equity_curve": [],
                "trades": [],
                "signals": []
            }

        closes = df['Close'].values
        sig_vals = signals.reindex(df.index).fillna(0).values

        cash = self.initial_capital
        shares = 0
        trades = []
        equity_records = []
        trade_signals = []

        current_entry_price = 0.0
        current_entry_date = ""
        current_entry_idx = 0

        # Benchmark: Buy and Hold using Initial Capital from day 0 Close (guarded against <= 0)
        day0_close = max(1e-4, float(closes[0]))
        bench_shares = (self.initial_capital * 0.99) / (day0_close * (1.0 + self.slippage_rate))
        bench_cash = self.initial_capital - bench_shares * day0_close

        for i in range(len(dates)):
            date = str(dates[i])
            close_price = max(1e-4, float(closes[i]))
            sig = int(sig_vals[i])
            
            # Check Stop Loss / Take Profit if currently holding
            exit_reason = None
            if shares > 0 and current_entry_price > 0:
                pnl_pct_current = (close_price - current_entry_price) / current_entry_price
                if self.stop_loss_pct is not None and pnl_pct_current <= -self.stop_loss_pct:
                    exit_reason = "STOP_LOSS"
                elif self.take_profit_pct is not None and pnl_pct_current >= self.take_profit_pct:
                    exit_reason = "TAKE_PROFIT"

            # Execute Exit if Stop Loss / Take Profit triggered OR signal is SELL (-1)
            if shares > 0 and (exit_reason is not None or sig < 0):
                exit_price = close_price * (1.0 - self.slippage_rate)
                gross_proceeds = shares * exit_price
                comm = self.calculate_commission(gross_proceeds)
                net_proceeds = gross_proceeds - comm
                cash += net_proceeds

                pnl = (exit_price - current_entry_price) * shares - comm
                pnl_pct = ((exit_price - current_entry_price) / current_entry_price) * 100.0
                holding_days = max(1, i - current_entry_idx)

                trades.append({
                    "trade_id": len(trades) + 1,
                    "type": "LONG",
                    "entry_date": current_entry_date,
                    "exit_date": date,
                    "entry_price": round(current_entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "shares": shares,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "holding_days": holding_days,
                    "exit_reason": exit_reason if exit_reason else "SIGNAL_SELL"
                })

                trade_signals.append({
                    "date": date,
                    "price": round(exit_price, 2),
                    "type": "SELL",
                    "reason": exit_reason if exit_reason else "SIGNAL_SELL"
                })

                shares = 0
                current_entry_price = 0.0
                current_entry_date = ""

            # Execute Entry if signal is BUY (1) and currently flat
            elif shares == 0 and sig > 0 and i < len(dates) - 1:
                exec_price = max(1e-4, close_price * (1.0 + self.slippage_rate))
                target_alloc = cash * self.position_size_pct
                if position_sizes is not None:
                    try:
                        raw_size = float(position_sizes.iloc[i]) if i < len(position_sizes) else 1.0
                        custom_size = 1.0 if (np.isnan(raw_size) or raw_size <= 0) else raw_size
                    except Exception:
                        custom_size = 1.0
                    target_alloc = min(cash * self.position_size_pct, cash * custom_size)

                order_shares = int(target_alloc / exec_price) if not np.isnan(target_alloc) else 0
                if order_shares > 0:
                    comm = self.calculate_commission(order_shares * exec_price)
                    total_cost = order_shares * exec_price + comm
                    if total_cost <= cash:
                        cash -= total_cost
                        shares = order_shares
                        current_entry_price = exec_price
                        current_entry_date = date
                        current_entry_idx = i

                        trade_signals.append({
                            "date": date,
                            "price": round(exec_price, 2),
                            "type": "BUY",
                            "reason": "SIGNAL_BUY"
                        })

            # Mark portfolio to market at end of day
            holdings_value = shares * close_price
            total_equity = cash + holdings_value
            benchmark_equity = bench_cash + bench_shares * close_price

            equity_records.append({
                "date": date,
                "equity": round(total_equity, 2),
                "cash": round(cash, 2),
                "holdings": round(holdings_value, 2),
                "close": round(close_price, 2),
                "benchmark": round(benchmark_equity, 2)
            })

        # Close any open trade at the end of backtest period
        if shares > 0:
            final_price = closes[-1] * (1.0 - self.slippage_rate)
            gross_proceeds = shares * final_price
            comm = self.calculate_commission(gross_proceeds)
            pnl = (final_price - current_entry_price) * shares - comm
            pnl_pct = ((final_price - current_entry_price) / current_entry_price) * 100.0
            trades.append({
                "trade_id": len(trades) + 1,
                "type": "LONG",
                "entry_date": current_entry_date,
                "exit_date": str(dates[-1]),
                "entry_price": round(current_entry_price, 2),
                "exit_price": round(final_price, 2),
                "shares": shares,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "holding_days": max(1, len(dates) - 1 - current_entry_idx),
                "exit_reason": "END_OF_PERIOD"
            })

            trade_signals.append({
                "date": str(dates[-1]),
                "price": round(final_price, 2),
                "type": "SELL",
                "reason": "END_OF_PERIOD"
            })

        # Calculate metrics and drawdowns with fast vectorized numpy operations
        eq_arr = np.array([r["equity"] for r in equity_records], dtype=np.float64)
        bench_arr = np.array([r["benchmark"] for r in equity_records], dtype=np.float64)

        peaks = np.maximum.accumulate(eq_arr)
        dds = np.where(peaks > 0, (eq_arr - peaks) / peaks, 0.0)
        dd_pcts = np.round(dds * 100.0, 2)

        for j, rec in enumerate(equity_records):
            rec["drawdown_pct"] = float(dd_pcts[j])

        date_indices = [r["date"] for r in equity_records]
        equity_series = pd.Series(eq_arr, index=date_indices)
        bench_series = pd.Series(bench_arr, index=date_indices)

        metrics = compute_performance_metrics(equity_series, bench_series, trades)

        return {
            "metrics": metrics,
            "equity_curve": equity_records,
            "trades": trades,
            "signals": trade_signals
        }
