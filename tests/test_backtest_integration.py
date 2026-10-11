import unittest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest_engine import BacktestEngine
from core.risk_manager import RiskManager
from strategies.portfolio_allocator import blend_multi_strategy_portfolio
from core.metrics import compute_performance_metrics

class TestBacktestIntegration(unittest.TestCase):
    def setUp(self):
        np.random.seed(123)
        n = 100
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        prices = [100.0]
        for _ in range(n - 1):
            prices.append(prices[-1] * (1.0 + np.random.randn() * 0.015))
        prices = np.array(prices)

        self.df = pd.DataFrame({
            "Open": prices * 0.998,
            "High": prices * 1.015,
            "Low": prices * 0.985,
            "Close": prices,
            "Volume": np.random.randint(1000000, 5000000, size=n)
        }, index=dates)

    def test_next_open_execution_timing(self):
        """
        Verify that a signal generated on day t executes at day t+1 Open,
        NOT day t Close.
        """
        signals = pd.Series(0, index=self.df.index)
        # Signal to BUY on day 10
        signals.iloc[10] = 1
        # Signal to SELL on day 20
        signals.iloc[20] = -1

        engine = BacktestEngine(
            initial_capital=100000.0,
            execution_mode="next_open",
            slippage_rate=0.0005,
            commission_rate=0.0005
        )
        res = engine.run(self.df, signals)

        trades = res["trades"]
        self.assertGreaterEqual(len(trades), 1)
        first_trade = trades[0]

        # Entry date must be day 11, NOT day 10!
        expected_entry_date = str(self.df.index[11])
        self.assertEqual(first_trade["entry_date"], expected_entry_date)

        # Expected entry price should be based on day 11 Open with slippage
        expected_fill_price = self.df["Open"].iloc[11] * (1.0 + 0.0005)
        self.assertAlmostEqual(first_trade["entry_price"], round(expected_fill_price, 2), places=1)

    def test_regulatory_fees_on_sell(self):
        """Verify SEC and FINRA regulatory fees are applied on SELL"""
        engine = BacktestEngine(
            initial_capital=100000.0,
            commission_rate=0.0005,
            min_commission=1.0
        )
        comm_buy = engine.calculate_commission(trade_value=50000.0, shares=500, action='BUY')
        comm_sell = engine.calculate_commission(trade_value=50000.0, shares=500, action='SELL')

        # SELL should be greater than BUY due to SEC fee and FINRA TAF
        self.assertGreater(comm_sell, comm_buy)
        # Verify SEC fee = 50000 * 0.0000278 = $1.39, FINRA TAF = 500 * 0.000166 = $0.083
        self.assertAlmostEqual(comm_sell - comm_buy, 50000.0 * 0.0000278 + 500 * 0.000166, places=2)

    def test_metrics_consistency(self):
        """Verify performance metrics calculation sanity"""
        dates = pd.date_range("2023-01-01", periods=60, freq="B")
        eq = pd.Series(np.linspace(100000, 120000, 60), index=dates)
        bn = pd.Series(np.linspace(100000, 110000, 60), index=dates)
        trades = [{
            "trade_id": 1, "pnl": 20000.0, "pnl_pct": 20.0, "holding_days": 60
        }]
        metrics = compute_performance_metrics(eq, bn, trades)

        self.assertAlmostEqual(metrics["total_return_pct"], 20.0, places=1)
        self.assertAlmostEqual(metrics["benchmark_return_pct"], 10.0, places=1)
        self.assertEqual(metrics["win_rate_pct"], 100.0)
        self.assertGreater(metrics["sharpe_ratio"], 0.0)

    def test_portfolio_blend(self):
        """Verify blending multiple strategies into portfolio"""
        dates = pd.date_range("2023-01-01", periods=50, freq="B")
        res1 = {
            "equity_curve": [{"date": str(d), "equity": 100000 + i * 100, "benchmark": 100000 + i * 50} for i, d in enumerate(dates)],
            "trades": []
        }
        res2 = {
            "equity_curve": [{"date": str(d), "equity": 100000 + i * 80, "benchmark": 100000 + i * 50} for i, d in enumerate(dates)],
            "trades": []
        }
        blended = blend_multi_strategy_portfolio(
            results_map={"s1": res1, "s2": res2},
            weights={"s1": 0.6, "s2": 0.4},
            initial_capital=100000.0
        )
        self.assertIn("metrics", blended)
        self.assertIn("correlation_matrix", blended)
        self.assertIn("equity_curve", blended)
        self.assertEqual(len(blended["equity_curve"]), 50)

if __name__ == "__main__":
    unittest.main()
