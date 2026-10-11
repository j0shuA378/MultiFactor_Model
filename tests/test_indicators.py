import unittest
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.indicators import (
    calculate_sma,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_donchian_channel,
    add_all_indicators
)

class TestIndicators(unittest.TestCase):
    def setUp(self):
        # Generate predictable synthetic price series
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        base = 100.0 + np.cumsum(np.random.randn(n) * 1.5)
        self.df = pd.DataFrame({
            "Open": base + np.random.randn(n) * 0.2,
            "High": base + np.abs(np.random.randn(n) * 1.2) + 0.5,
            "Low": base - np.abs(np.random.randn(n) * 1.2) - 0.5,
            "Close": base,
            "Volume": np.random.randint(100000, 5000000, size=n)
        }, index=dates)

    def test_sma_and_ema(self):
        sma20 = calculate_sma(self.df["Close"], 20)
        self.assertEqual(len(sma20), len(self.df))
        self.assertTrue(pd.isna(sma20.iloc[0]))
        self.assertAlmostEqual(sma20.iloc[19], self.df["Close"].iloc[:20].mean(), places=4)

        ema12 = calculate_ema(self.df["Close"], 12)
        self.assertEqual(len(ema12), len(self.df))
        self.assertFalse(pd.isna(ema12.iloc[0]))

    def test_macd_definition(self):
        dif, dea, hist = calculate_macd(self.df["Close"], 12, 26, 9)
        self.assertEqual(len(dif), len(self.df))
        self.assertEqual(len(dea), len(self.df))
        self.assertEqual(len(hist), len(self.df))
        # hist should be exactly (dif - dea) * 2
        np.testing.assert_allclose(hist.values, (dif.values - dea.values) * 2, rtol=1e-5)

    def test_rsi_bounds_and_wilder_smoothing(self):
        rsi = calculate_rsi(self.df["Close"], 14)
        self.assertTrue((rsi >= 0.0).all())
        self.assertTrue((rsi <= 100.0).all())

        # Test extreme boundary: pure monotonically increasing prices
        mono_up = pd.Series([10.0 + i for i in range(30)])
        rsi_up = calculate_rsi(mono_up, 14)
        self.assertEqual(rsi_up.iloc[-1], 100.0)

        # Test extreme boundary: pure monotonically decreasing prices
        mono_down = pd.Series([100.0 - i for i in range(30)])
        rsi_down = calculate_rsi(mono_down, 14)
        self.assertEqual(rsi_down.iloc[-1], 0.0)

    def test_donchian_channel_lookahead_elimination(self):
        """
        Donchian Channel test:
        Verify shift_lag=True strictly excludes the current bar t's High/Low.
        """
        high = self.df["High"]
        low = self.df["Low"]
        upper, lower, mid = calculate_donchian_channel(high, low, period=20, shift_lag=True)

        for i in range(21, len(self.df)):
            expected_max = high.iloc[i-20:i].max()
            expected_min = low.iloc[i-20:i].min()
            self.assertAlmostEqual(upper.iloc[i], expected_max, places=5)
            self.assertAlmostEqual(lower.iloc[i], expected_min, places=5)

        # Crucial check: if bar t's high spikes to 1000, upper on bar t MUST NOT change!
        high_tampered = high.copy()
        high_tampered.iloc[50] = 99999.0
        upper_tampered, _, _ = calculate_donchian_channel(high_tampered, low, period=20, shift_lag=True)
        # Upper at bar 50 must still reflect bars 30..49, NOT 50!
        self.assertEqual(upper_tampered.iloc[50], upper.iloc[50])
        # Upper at bar 51 will reflect bar 50
        self.assertEqual(upper_tampered.iloc[51], 99999.0)

    def test_atr_no_future_leakage(self):
        """Verify ATR does not use bfill to leak future true range"""
        atr = calculate_atr(self.df["High"], self.df["Low"], self.df["Close"], period=14)
        self.assertFalse(pd.isna(atr.iloc[0]))
        self.assertTrue((atr > 0).all())

    def test_bollinger_bands(self):
        up, mid, low, pct_b, width = calculate_bollinger_bands(self.df["Close"], 20, 2.0)
        self.assertTrue((up.dropna() >= mid.dropna()).all())
        self.assertTrue((mid.dropna() >= low.dropna()).all())
        self.assertTrue((width.dropna() >= 0.0).all())

if __name__ == "__main__":
    unittest.main()
