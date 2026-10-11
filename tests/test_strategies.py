import unittest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.ml_predictor import MLPredictorStrategy
from strategies.turtle_grid import TurtleGridStrategy

class TestStrategies(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        n = 160
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        # Generate an oscillating series with clear breakout trend in the middle
        t = np.linspace(0, 4 * np.pi, n)
        trend = np.linspace(100.0, 160.0, n)
        cycle = 10.0 * np.sin(t)
        noise = np.random.randn(n) * 1.5
        close_p = trend + cycle + noise
        
        self.df = pd.DataFrame({
            "Open": close_p - 0.5 + np.random.randn(n) * 0.3,
            "High": close_p + np.abs(np.random.randn(n) * 1.5) + 0.8,
            "Low": close_p - np.abs(np.random.randn(n) * 1.5) - 0.8,
            "Close": close_p,
            "Volume": np.random.randint(1000000, 5000000, size=n)
        }, index=dates)

    def test_multi_factor_momentum_strategy(self):
        strat = MultiFactorMomentumStrategy()
        sigs, meta = strat.generate_signals(self.df)

        self.assertEqual(len(sigs), len(self.df))
        self.assertTrue(set(sigs.unique()).issubset({-1, 0, 1}))
        self.assertIn("overall_ic", meta)
        self.assertIn("factor_ir", meta)
        self.assertIn("current_regime", meta)
        self.assertIn("position_sizes", meta)
        self.assertIn("sub_factor_ics", meta)
        self.assertTrue(len(meta["position_sizes"]) == len(self.df))

    def test_ml_predictor_strategy(self):
        strat = MLPredictorStrategy(params={"n_walk_splits": 2, "n_estimators": 30})
        sigs, meta = strat.generate_signals(self.df)

        self.assertEqual(len(sigs), len(self.df))
        self.assertTrue(set(sigs.unique()).issubset({-1, 0, 1}))
        self.assertIn("f1_score", meta)
        self.assertIn("pr_auc", meta)
        self.assertIn("brier_score", meta)
        self.assertIn("decision_thresholds", meta)
        self.assertIn("feature_importances", meta)
        self.assertTrue(len(meta["feature_importances"]) > 0)

    def test_turtle_grid_strategy(self):
        strat = TurtleGridStrategy(params={"max_units": 4, "system_type": "s1"})
        sigs, meta = strat.generate_signals(self.df)

        self.assertEqual(len(sigs), len(self.df))
        self.assertTrue(set(sigs.unique()).issubset({-1, 0, 1}))
        self.assertIn("entry_upper", meta)
        self.assertIn("exit_lower", meta)
        self.assertIn("position_sizes", meta)
        # Position sizes should never exceed 1.0 (max_leverage)
        self.assertTrue((meta["position_sizes"] <= 1.0).all())

if __name__ == "__main__":
    unittest.main()
