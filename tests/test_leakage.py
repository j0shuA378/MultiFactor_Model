import unittest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.indicators import add_all_indicators
from strategies.factor_momentum import MultiFactorMomentumStrategy
from strategies.turtle_grid import TurtleGridStrategy
from strategies.ml_predictor import MLPredictorStrategy

class TestFutureLeakage(unittest.TestCase):
    """
    严密未来函数与数据泄漏审计测试 (Strict Future Leakage Audit)
    测试逻辑:
    若策略或指标在时刻 t 的决策仅依赖于 t 及其之前的信息，
    则随意篡改 t+1 至末尾的所有未来价格数据，时刻 t 的指标与信号必须绝对保持一致！
    """
    def setUp(self):
        np.random.seed(101)
        n = 150
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        base = 150.0 + np.cumsum(np.random.randn(n) * 2.0)
        self.df = pd.DataFrame({
            "Open": base + np.random.randn(n) * 0.5,
            "High": base + np.abs(np.random.randn(n) * 1.5) + 0.8,
            "Low": base - np.abs(np.random.randn(n) * 1.5) - 0.8,
            "Close": base,
            "Volume": np.random.randint(500000, 3000000, size=n)
        }, index=dates)

    def test_indicator_pipeline_leak_free(self):
        t_eval = 80
        df_orig = self.df.copy()
        ind_orig = add_all_indicators(df_orig)

        # Mutate future rows > t_eval aggressively
        df_mutated = self.df.copy()
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Open")] *= 5.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("High")] *= 8.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Low")] *= 0.2
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Close")] *= 6.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Volume")] *= 20.0

        ind_mutated = add_all_indicators(df_mutated)

        # Verify every indicator value at and before t_eval is identical
        for col in ind_orig.columns:
            if col in ["Open", "High", "Low", "Close", "Volume"]:
                continue
            orig_vals = ind_orig[col].iloc[:t_eval + 1].dropna().values
            mut_vals = ind_mutated[col].iloc[:t_eval + 1].dropna().values
            np.testing.assert_allclose(
                orig_vals, mut_vals, rtol=1e-5, atol=1e-5,
                err_msg=f"Indicator {col} leaked future data into past bars!"
            )

    def test_turtle_strategy_leak_free(self):
        t_eval = 90
        strat = TurtleGridStrategy()
        sigs_orig, _ = strat.generate_signals(self.df)

        df_mutated = self.df.copy()
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("High")] *= 5.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Close")] *= 5.0

        strat_mut = TurtleGridStrategy()
        sigs_mut, _ = strat_mut.generate_signals(df_mutated)

        # Signals up to t_eval must be identical
        np.testing.assert_array_equal(
            sigs_orig.iloc[:t_eval + 1].values,
            sigs_mut.iloc[:t_eval + 1].values,
            err_msg="TurtleGridStrategy leaked future data into past signals!"
        )

    def test_factor_momentum_leak_free(self):
        t_eval = 85
        strat = MultiFactorMomentumStrategy()
        sigs_orig, _ = strat.generate_signals(self.df)

        df_mutated = self.df.copy()
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Close")] *= 4.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("High")] *= 4.0

        strat_mut = MultiFactorMomentumStrategy()
        sigs_mut, _ = strat_mut.generate_signals(df_mutated)

        np.testing.assert_array_equal(
            sigs_orig.iloc[:t_eval + 1].values,
            sigs_mut.iloc[:t_eval + 1].values,
            err_msg="MultiFactorMomentumStrategy leaked future data into past signals!"
        )

    def test_ml_features_leak_free(self):
        t_eval = 75
        strat = MLPredictorStrategy()
        feats_orig, _ = strat.extract_features(self.df)

        df_mutated = self.df.copy()
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("Close")] *= 3.0
        df_mutated.iloc[t_eval + 1:, df_mutated.columns.get_loc("High")] *= 3.0

        feats_mut, _ = strat.extract_features(df_mutated)

        for col in feats_orig.columns:
            orig_vals = feats_orig[col].iloc[:t_eval + 1].dropna().values
            mut_vals = feats_mut[col].iloc[:t_eval + 1].dropna().values
            np.testing.assert_allclose(
                orig_vals, mut_vals, rtol=1e-5, atol=1e-5,
                err_msg=f"ML feature '{col}' leaked future data!"
            )

if __name__ == "__main__":
    unittest.main()
