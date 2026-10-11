import unittest
import numpy as np
import pandas as pd
from core.chan_theory import (
    merge_kline_inclusions,
    find_fractals,
    construct_standard_bis,
    compute_zhongshus,
    detect_chan_buy_sell_points,
    run_chan_analysis,
    calculate_risk_budget_position,
    DivergenceType
)
from strategies.chan_strategy import ChanTheoryStrategy
from core.backtest_engine import BacktestEngine

class TestChanTheory(unittest.TestCase):
    def setUp(self):
        # 构造基准测试时序 (模拟上涨、中枢震荡与突破)
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        prices = 100.0 + np.sin(np.linspace(0, 15, 100)) * 10.0 + np.linspace(0, 20, 100)
        highs = prices + np.random.uniform(0.5, 1.5, 100)
        lows = prices - np.random.uniform(0.5, 1.5, 100)
        opens = lows + (highs - lows) * 0.4
        closes = prices
        vols = np.random.randint(100000, 500000, 100)

        self.df = pd.DataFrame({
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": vols
        }, index=dates)

    def test_merge_kline_inclusions(self):
        # 验证包含合并无报错且输出合法
        merged = merge_kline_inclusions(self.df)
        self.assertIsInstance(merged, list)
        self.assertGreater(len(merged), 0)
        self.assertLessEqual(len(merged), len(self.df))
        for b in merged:
            self.assertGreaterEqual(b.high, b.low)

    def test_fractals_and_bis(self):
        merged = merge_kline_inclusions(self.df)
        fractals = find_fractals(merged)
        self.assertIsInstance(fractals, list)
        
        bis = construct_standard_bis(fractals, merged)
        self.assertIsInstance(bis, list)
        # 笔的顶底应当交替且跨度合法
        for bi in bis:
            self.assertIn(bi.direction, [1, -1])
            self.assertGreater(bi.high, bi.low)

    def test_run_chan_analysis(self):
        res = run_chan_analysis(self.df)
        self.assertEqual(res["status"], "success")
        self.assertIn("signals", res)
        self.assertIn("tags", res)
        self.assertEqual(len(res["signals"]), len(self.df))

    def test_risk_budget_calculation(self):
        # 1. 正常波动测试: 股价 100 元, 止损 95 元 (物理风险 5 元), 净值 200,000 元, 风险预算 2% (4,000 元)
        # 目标股数 = 4000 / 5 = 800 股 (80,000 元，占净值 40% <= 50%上限)
        res = calculate_risk_budget_position(
            account_equity=200000.0,
            entry_price=100.0,
            stop_loss_price=95.0,
            risk_per_trade=0.02,
            max_position_ratio=0.50,
            lot_size=100
        )
        self.assertEqual(res.shares, 800)
        self.assertAlmostEqual(res.risk_amount, 4000.0, places=2)
        self.assertAlmostEqual(res.position_ratio, 0.40, places=2)

        # 2. 窄幅止损上限截断测试: 股价 100 元, 止损 99.5 元 (风险仅 0.5 元)
        # 理论股数 = 4000 / 0.5 = 8000 股 (80万资金)，必须被 30% 上限 (6万资金 = 600股) 截断
        res_capped = calculate_risk_budget_position(
            account_equity=200000.0,
            entry_price=100.0,
            stop_loss_price=99.5,
            risk_per_trade=0.02,
            max_position_ratio=0.30,
            lot_size=100
        )
        self.assertEqual(res_capped.shares, 600)
        self.assertLessEqual(res_capped.position_ratio, 0.30)

    def test_chan_strategy_backtest(self):
        strat = ChanTheoryStrategy()
        signals, meta = strat.generate_signals(self.df)
        self.assertEqual(len(signals), len(self.df))
        self.assertIn("strategy_type", meta)
        self.assertIn("risk_budget_profile", meta)

        engine = BacktestEngine(initial_capital=100000.0)
        res = engine.run(self.df, signals)
        self.assertIn("metrics", res)
        metrics = res["metrics"]
        self.assertIn("total_return_pct", metrics)
        self.assertIn("max_drawdown_pct", metrics)
        self.assertIn("win_rate_pct", metrics)

if __name__ == "__main__":
    unittest.main()
