import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.risk_manager import RiskManager

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager(
            max_single_position_pct=0.25,
            max_portfolio_leverage=1.0,
            cash_buffer_pct=0.02,              # 2% cash buffer
            max_drawdown_circuit_breaker=0.10,  # 10% max DD circuit breaker
            daily_loss_circuit_breaker=0.03     # 3% daily DD circuit breaker
        )
        self.rm.reset_state(initial_equity=100000.0)

    def test_cash_buffer_enforcement(self):
        # Account has $100,000 equity, but only $2,500 cash remaining
        # Minimum cash buffer is 2% of $100k = $2,000. Usable cash is $500.
        # Attempt to buy $3,000 worth of stock at $100/share -> should downsize to <= 5 shares
        approved, reason, shares = self.rm.validate_order(
            action='BUY',
            shares=30,
            price=100.0,
            current_cash=2500.0,
            total_equity=100000.0
        )
        self.assertTrue(approved)
        self.assertLessEqual(shares * 100.0, 500.0)

        # If cash is strictly less than buffer ($1,500 < $2,000 buffer), reject entirely
        approved2, reason2, shares2 = self.rm.validate_order(
            action='BUY',
            shares=10,
            price=100.0,
            current_cash=1500.0,
            total_equity=100000.0
        )
        self.assertFalse(approved2)
        self.assertEqual(shares2, 0)
        self.assertIn("可用现金不足", reason2)

    def test_single_position_concentration_limit(self):
        # Max single position is 25% of $100k = $25,000
        # Already holding $20,000. Attempt to buy another $10,000 -> downsized to $5,000 (50 shares at $100)
        approved, reason, shares = self.rm.validate_order(
            action='BUY',
            shares=100,
            price=100.0,
            current_cash=50000.0,
            total_equity=100000.0,
            current_position_mv=20000.0
        )
        self.assertTrue(approved)
        self.assertEqual(shares, 50)

    def test_drawdown_circuit_breaker(self):
        # Initial equity: $100,000. Peak equity: $100,000.
        # Watermark drops to $88,000 (12% drawdown > 10% threshold)
        status = self.rm.update_equity_checkpoint(88000.0)
        self.assertTrue(status["circuit_breaker_active"])
        self.assertIn("熔断", status["circuit_breaker_reason"])

        # Any subsequent BUY order must be strictly rejected
        approved, reason, shares = self.rm.validate_order(
            action='BUY',
            shares=10,
            price=50.0,
            current_cash=50000.0,
            total_equity=88000.0
        )
        self.assertFalse(approved)
        self.assertIn("开仓拒绝", reason)

        # SELL order to close or reduce risk MUST still be approved
        approved_sell, _, _ = self.rm.validate_order(
            action='SELL',
            shares=10,
            price=50.0,
            current_cash=50000.0,
            total_equity=88000.0
        )
        self.assertTrue(approved_sell)

    def test_turtle_volatility_unit_sizing(self):
        # Equity = $100,000, 1% risk = $1,000.
        # ATR N = $5.00.
        # Unit = $1,000 / $5.00 = 200 shares.
        units = self.rm.compute_turtle_position_units(
            equity=100000.0,
            atr_n=5.0,
            risk_pct_per_trade=0.01,
            contract_multiplier=1.0
        )
        self.assertEqual(units, 200)

if __name__ == "__main__":
    unittest.main()
