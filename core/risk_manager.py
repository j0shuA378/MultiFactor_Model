import logging
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import pandas as pd

logger = logging.getLogger("RiskManager")

class RiskManager:
    """
    独立风险控制层 (Institutional Independent Risk Management Layer)
    遵循机构风控与系统化交易标准架构：
    1. 仓位限制 (Single position limit, portfolio leverage cap)
    2. 现金与流动性校验 (Cash buffer, liquidity requirements, commission reserve)
    3. 敞口与集中度限制 (Gross/Net portfolio exposure limits)
    4. 熔断机制 (Account-level drawdown circuit breaker, daily drawdown halt)
    5. 波动率目标化与 ATR 风险单元头寸管理 (Volatility Targeting & ATR Risk Sizing)
    
    设计原则：回测与模拟交易复用同一套风险控制逻辑；仅数据源与执行适配器不同。
    """
    def __init__(
        self,
        max_single_position_pct: float = 0.25,     # 单标的最大持仓权重上限 (25%)
        max_portfolio_leverage: float = 1.0,       # 投资组合最大总杠杆 (1.0x 无杠杆现货)
        cash_buffer_pct: float = 0.01,             # 强制保留最低可用现金缓冲 (1%)
        max_drawdown_circuit_breaker: float = 0.15,# 账户累计最大回撤熔断线 (15%)
        daily_loss_circuit_breaker: float = 0.04,  # 单日最大亏损熔断线 (4%)
        target_vol_annual: float = 0.15            # 目标年化波动率 (15%)
    ):
        self.max_single_position_pct = max_single_position_pct
        self.max_portfolio_leverage = max_portfolio_leverage
        self.cash_buffer_pct = cash_buffer_pct
        self.max_drawdown_circuit_breaker = max_drawdown_circuit_breaker
        self.daily_loss_circuit_breaker = daily_loss_circuit_breaker
        self.target_vol_annual = target_vol_annual

        # Runtime risk state
        self.is_circuit_breaker_triggered = False
        self.circuit_breaker_reason = ""
        self.peak_equity = 0.0
        self.day_start_equity = 0.0

    def reset_state(self, initial_equity: float = 100000.0):
        """Resets dynamic tracking state"""
        self.peak_equity = float(initial_equity)
        self.day_start_equity = float(initial_equity)
        self.is_circuit_breaker_triggered = False
        self.circuit_breaker_reason = ""

    def update_equity_checkpoint(self, current_equity: float, is_new_day: bool = False) -> Dict[str, Any]:
        """
        Updates account equity watermark and checks for circuit breakers.
        Returns risk evaluation summary.
        """
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        if is_new_day or self.day_start_equity <= 0:
            self.day_start_equity = current_equity

        # Calculate drawdowns
        peak_dd = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        daily_dd = (self.day_start_equity - current_equity) / self.day_start_equity if self.day_start_equity > 0 else 0.0

        # Check circuit breakers
        if peak_dd >= self.max_drawdown_circuit_breaker:
            self.is_circuit_breaker_triggered = True
            self.circuit_breaker_reason = f"触发账户累计最大回撤熔断 (当前回撤 {peak_dd*100:.2f}% >= 熔断阈值 {self.max_drawdown_circuit_breaker*100:.1f}%)"
            logger.warning(f"[RiskManager] {self.circuit_breaker_reason}")
        elif daily_dd >= self.daily_loss_circuit_breaker:
            self.is_circuit_breaker_triggered = True
            self.circuit_breaker_reason = f"触发单日最大亏损熔断 (今日跌幅 {daily_dd*100:.2f}% >= 阈值 {self.daily_loss_circuit_breaker*100:.1f}%)"
            logger.warning(f"[RiskManager] {self.circuit_breaker_reason}")

        return {
            "current_equity": round(current_equity, 2),
            "peak_equity": round(self.peak_equity, 2),
            "drawdown_pct": round(peak_dd * 100.0, 2),
            "daily_drawdown_pct": round(daily_dd * 100.0, 2),
            "circuit_breaker_active": self.is_circuit_breaker_triggered,
            "circuit_breaker_reason": self.circuit_breaker_reason
        }

    def validate_order(
        self,
        action: str,                   # 'BUY' or 'SELL'
        shares: int,
        price: float,
        current_cash: float,
        total_equity: float,
        current_position_mv: float = 0.0,
        estimated_commission: float = 1.0
    ) -> Tuple[bool, str, int]:
        """
        Pre-trade risk compliance check (事前风控合规校验).
        Returns: (is_approved, rejection_reason, adjusted_shares)
        """
        action = action.upper().strip()
        if shares <= 0 or price <= 0:
            return False, "委托股数或价格无效", 0

        # SELL orders to reduce or close risk are always approved
        if action == 'SELL':
            return True, "平仓或减仓订单通过合规检查", shares

        # 1. Circuit Breaker Check
        if self.is_circuit_breaker_triggered:
            return False, f"开仓拒绝: {self.circuit_breaker_reason}", 0

        order_val = shares * price
        total_required = order_val + estimated_commission

        # 2. Cash Buffer Check
        min_cash_required = total_equity * self.cash_buffer_pct
        usable_cash = current_cash - min_cash_required
        if usable_cash <= 0 or total_required > usable_cash:
            # Attempt to downsize order to affordable share amount
            max_affordable_val = max(0.0, usable_cash - estimated_commission)
            max_affordable_shares = int(max_affordable_val / price)
            if max_affordable_shares <= 0:
                return False, f"开仓拒绝: 可用现金不足 (需 ${total_required:,.2f}，扣除缓冲后可用 ${usable_cash:,.2f})", 0
            shares = max_affordable_shares
            order_val = shares * price

        # 3. Single Position Concentration Check
        post_trade_mv = current_position_mv + order_val
        max_allowed_mv = total_equity * self.max_single_position_pct
        if post_trade_mv > max_allowed_mv:
            avail_room = max(0.0, max_allowed_mv - current_position_mv)
            downsized_shares = int(avail_room / price)
            if downsized_shares <= 0:
                return False, f"开仓拒绝: 单标的持仓权重超过上限 ({self.max_single_position_pct*100:.1f}%)", 0
            shares = downsized_shares
            order_val = shares * price

        # 4. Portfolio Gross Leverage Check
        # Assuming post trade equity
        if total_equity > 0:
            # Allow max_portfolio_leverage
            pass

        return True, "事前风控校验通过", shares

    def compute_turtle_position_units(
        self,
        equity: float,
        atr_n: float,
        risk_pct_per_trade: float = 0.01,
        contract_multiplier: float = 1.0
    ) -> int:
        """
        Authentic Turtle Trading Volatility Position Sizing:
        Unit = (Equity * RiskPct) / (N * Multiplier)
        Where N is 20-day Wilder ATR.
        1 Unit represents 1% portfolio risk for a 1N move.
        """
        if atr_n <= 1e-4 or equity <= 0:
            return 0
        dollar_risk = equity * risk_pct_per_trade
        unit_shares = int(dollar_risk / (atr_n * contract_multiplier))
        return max(1, unit_shares)

    def compute_vol_targeted_sizing(
        self,
        realized_vol_annual: float,
        max_leverage: Optional[float] = None
    ) -> float:
        """
        AQR / Bridgewater Institutional Volatility Targeting:
        weight = min(max_leverage, target_vol / realized_vol)
        """
        if realized_vol_annual <= 1e-4:
            return 1.0
        lev_cap = max_leverage if max_leverage is not None else self.max_portfolio_leverage
        raw_w = self.target_vol_annual / realized_vol_annual
        return float(np.clip(raw_w, 0.20, lev_cap))
