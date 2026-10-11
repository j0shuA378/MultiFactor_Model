import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from core.metrics import compute_performance_metrics
from core.risk_manager import RiskManager

class BacktestEngine:
    """
    机构级事件驱动与无未来函数回测引擎 (Institutional Realistic Execution Backtest Engine)
    
    1. 真实交易执行时序 (Realistic Execution Model):
       - 默认模式 'next_open': 当日收盘产生信号，于次日开盘价 (T+1 Open) 执行成交，严禁当日收盘即时成交的同Bar偷价与未来函数
       - 可选模式 'same_close': 仅在特定日终撮合假设下使用
    2. 机构交易成本与规费模型 (Institutional Friction & Regulatory Fees):
       - 券商佣金 (Broker Commission, e.g. 0.05%, min $1.00)
       - 滑点模型 (Bid-Ask Spread Slippage, e.g. 0.05%)
       - SEC 规费 (SEC Transaction Fee: $0.0000278 on SELL)
       - FINRA TAF 规费 (Trading Activity Fee: $0.000166/share on SELL, max $8.30)
    3. 集成独立风险控制层 (RiskManager Integration):
       - 仓位集中度上限与杠杆控制
       - 可用现金与流动性缓冲校验
       - 账户级最大回撤与单日亏损熔断机制 (Circuit Breakers)
    4. 逐日盯市与矢量化绩效评估 (Mark-to-Market Accounting):
       - 真实权益曲线记录，精准收益率、夏普、回撤与盈亏比核算
    """
    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0005,        # 0.05% 佣金率
        min_commission: float = 1.0,            # 单笔最低佣金 $1.00
        slippage_rate: float = 0.0005,          # 0.05% 滑点
        execution_mode: str = "next_open",      # 'next_open' (标准实盘时序) 或 'same_close'
        position_size_pct: float = 0.95,        # 最大单次资金分配
        stop_loss_pct: Optional[float] = None,  # 策略外挂止损百分比 (e.g. 0.05 for 5%)
        take_profit_pct: Optional[float] = None,# 策略外挂止盈百分比 (e.g. 0.15 for 15%)
        risk_manager: Optional[RiskManager] = None
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_rate = slippage_rate
        self.execution_mode = execution_mode
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        # Independent Risk Manager
        self.risk_manager = risk_manager or RiskManager()

    def calculate_commission(self, trade_value: float, shares: int, action: str) -> float:
        """
        Calculates institutional trade cost:
        Broker commission + SEC fee + FINRA TAF fee (on SELL)
        """
        broker_comm = max(self.min_commission, trade_value * self.commission_rate)
        regulatory_fees = 0.0
        if action.upper() == 'SELL':
            # US SEC Section 31 Fee
            sec_fee = trade_value * 0.0000278
            # FINRA Trading Activity Fee (TAF)
            finra_taf = min(8.30, shares * 0.000166)
            regulatory_fees = sec_fee + finra_taf

        return broker_comm + regulatory_fees

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        position_sizes: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Executes backtest across timeline.
        df: OHLCV DataFrame indexed by Date
        signals: Series of integer signals (-1: Exit/Sell, 1: Enter/Buy, 0: Hold)
        position_sizes: Series of sizing fractions (0.0 to 1.0)
        """
        dates = df.index.tolist()
        n = len(dates)
        if n == 0:
            return {"metrics": {}, "equity_curve": [], "trades": [], "signals": []}

        closes = df['Close'].values
        opens = df['Open'].values if 'Open' in df.columns else closes
        highs = df['High'].values if 'High' in df.columns else closes
        lows = df['Low'].values if 'Low' in df.columns else closes

        sig_vals = signals.reindex(df.index).fillna(0).values

        # Reset Risk Manager
        self.risk_manager.reset_state(initial_equity=self.initial_capital)

        cash = self.initial_capital
        shares = 0
        trades = []
        equity_records = []
        trade_signals = []

        current_entry_price = 0.0
        current_entry_comm = 0.0
        current_entry_date = ""
        current_entry_idx = 0

        # Pending signal to be executed on the next bar (T+1 Open)
        pending_signal = 0
        pending_signal_date = ""
        pending_pos_size = 1.0

        # Benchmark: Buy and Hold using Initial Capital from day 0 Open
        day0_exec_price = max(1e-4, float(opens[0])) * (1.0 + self.slippage_rate)
        bench_alloc = self.initial_capital * 0.99
        bench_shares = int(bench_alloc / day0_exec_price)
        bench_comm = self.calculate_commission(bench_shares * day0_exec_price, bench_shares, 'BUY')
        bench_cash = self.initial_capital - (bench_shares * day0_exec_price + bench_comm)

        for i in range(n):
            date = str(dates[i])
            open_p = max(1e-4, float(opens[i]))
            high_p = max(1e-4, float(highs[i]))
            low_p = max(1e-4, float(lows[i]))
            close_p = max(1e-4, float(closes[i]))

            # Current bar's incoming signal generated at bar i
            cur_signal = int(sig_vals[i])
            cur_pos_size = float(position_sizes.iloc[i]) if (position_sizes is not None and i < len(position_sizes)) else 1.0

            # -------------------------------------------------------------
            # 1. 真实时序成交撮合 (Execute Pending Signal at Bar i Open)
            # -------------------------------------------------------------
            # Check Stop Loss / Take Profit on open/intraday if holding
            intraday_exit_reason = None
            if shares > 0 and current_entry_price > 0:
                # Worst-case drawdown check intraday
                intraday_pnl_pct = (low_p - current_entry_price) / current_entry_price
                intraday_profit_pct = (high_p - current_entry_price) / current_entry_price

                if self.stop_loss_pct is not None and intraday_pnl_pct <= -self.stop_loss_pct:
                    intraday_exit_reason = "STOP_LOSS"
                elif self.take_profit_pct is not None and intraday_profit_pct >= self.take_profit_pct:
                    intraday_exit_reason = "TAKE_PROFIT"

            # Check if pending order needs to execute at Open
            exec_signal = 0
            exec_price = open_p
            exec_date = date

            if self.execution_mode == "next_open":
                if pending_signal != 0:
                    exec_signal = pending_signal
                    exec_price = open_p
                    pending_signal = 0
                elif intraday_exit_reason is not None and shares > 0:
                    exec_signal = -1
                    exec_price = max(1e-4, current_entry_price * (1.0 - (self.stop_loss_pct or 0.05)))
            else:
                # same_close execution mode
                exec_signal = cur_signal
                exec_price = close_p

            # --- 执行平仓 / 卖出 ---
            if shares > 0 and (exec_signal < 0 or intraday_exit_reason is not None):
                exit_fill_price = max(1e-4, exec_price * (1.0 - self.slippage_rate))
                gross_proceeds = shares * exit_fill_price
                comm = self.calculate_commission(gross_proceeds, shares, 'SELL')
                net_proceeds = gross_proceeds - comm
                cash += net_proceeds

                pnl = (exit_fill_price - current_entry_price) * shares - (current_entry_comm + comm)
                pnl_pct = ((exit_fill_price - current_entry_price) / current_entry_price) * 100.0
                holding_days = max(1, i - current_entry_idx)

                reason_str = intraday_exit_reason if intraday_exit_reason else "SIGNAL_SELL"

                trades.append({
                    "trade_id": len(trades) + 1,
                    "type": "LONG",
                    "entry_date": current_entry_date,
                    "exit_date": date,
                    "entry_price": round(current_entry_price, 2),
                    "exit_price": round(exit_fill_price, 2),
                    "shares": shares,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "holding_days": holding_days,
                    "exit_reason": reason_str
                })

                trade_signals.append({
                    "date": date,
                    "price": round(exit_fill_price, 2),
                    "type": "SELL",
                    "reason": reason_str
                })

                shares = 0
                current_entry_price = 0.0
                current_entry_comm = 0.0
                current_entry_date = ""

            # --- 执行开仓 / 买入 ---
            elif shares == 0 and exec_signal > 0 and i < n - 1:
                buy_fill_price = max(1e-4, exec_price * (1.0 + self.slippage_rate))
                total_equity = cash
                # Risk manager validation
                is_approved, reject_msg, approved_shares = self.risk_manager.validate_order(
                    action='BUY',
                    shares=int((cash * self.position_size_pct * min(1.0, max(0.2, pending_pos_size))) / buy_fill_price),
                    price=buy_fill_price,
                    current_cash=cash,
                    total_equity=total_equity
                )

                if is_approved and approved_shares > 0:
                    comm = self.calculate_commission(approved_shares * buy_fill_price, approved_shares, 'BUY')
                    while approved_shares > 0 and (approved_shares * buy_fill_price + comm) > cash:
                        approved_shares -= 1
                        comm = self.calculate_commission(approved_shares * buy_fill_price, approved_shares, 'BUY')

                    if approved_shares > 0:
                        total_cost = approved_shares * buy_fill_price + comm
                        cash -= total_cost
                        shares = approved_shares
                        current_entry_price = buy_fill_price
                        current_entry_comm = comm
                        current_entry_date = date
                        current_entry_idx = i

                        trade_signals.append({
                            "date": date,
                            "price": round(buy_fill_price, 2),
                            "type": "BUY",
                            "reason": "SIGNAL_BUY"
                        })

            # -------------------------------------------------------------
            # 2. 调度次日执行信号 (Queue Signal for T+1 Open)
            # -------------------------------------------------------------
            if self.execution_mode == "next_open":
                if cur_signal != 0:
                    pending_signal = cur_signal
                    pending_signal_date = date
                    pending_pos_size = cur_pos_size
                else:
                    pending_signal = 0

            # -------------------------------------------------------------
            # 3. 逐日盯市结算 (End-of-Day Mark to Market)
            # -------------------------------------------------------------
            holdings_value = shares * close_p
            total_equity = cash + holdings_value
            benchmark_equity = bench_cash + bench_shares * close_p

            # Update Risk Manager equity watermark
            self.risk_manager.update_equity_checkpoint(total_equity, is_new_day=True)

            equity_records.append({
                "date": date,
                "equity": round(total_equity, 2),
                "cash": round(cash, 2),
                "holdings": round(holdings_value, 2),
                "close": round(close_p, 2),
                "benchmark": round(benchmark_equity, 2)
            })

        # -------------------------------------------------------------
        # 4. 回测期末平仓处理 (End of Backtest Period Cleanup)
        # -------------------------------------------------------------
        if shares > 0:
            final_price = closes[-1] * (1.0 - self.slippage_rate)
            gross_proceeds = shares * final_price
            comm = self.calculate_commission(gross_proceeds, shares, 'SELL')
            pnl = (final_price - current_entry_price) * shares - (current_entry_comm + comm)
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
                "holding_days": max(1, n - 1 - current_entry_idx),
                "exit_reason": "END_OF_PERIOD"
            })

            trade_signals.append({
                "date": str(dates[-1]),
                "price": round(final_price, 2),
                "type": "SELL",
                "reason": "END_OF_PERIOD"
            })

            cash += (gross_proceeds - comm)
            equity_records[-1]["equity"] = round(cash, 2)
            equity_records[-1]["cash"] = round(cash, 2)
            equity_records[-1]["holdings"] = 0.0
            shares = 0

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
            "signals": trade_signals,
            "execution_mode": self.execution_mode
        }
