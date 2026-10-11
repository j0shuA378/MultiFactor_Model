import unittest
from core.data_loader import (
    sanitize_ticker,
    search_yahoo_tickers,
    get_ticker_metadata,
    fetch_realtime_quote,
    FALLBACK_STOCKS
)

class TestDataLoader(unittest.TestCase):
    def test_sanitize_ticker(self):
        self.assertEqual(sanitize_ticker("600519"), "600519.SS")
        self.assertEqual(sanitize_ticker("000001"), "000001.SZ")
        self.assertEqual(sanitize_ticker("0700"), "0700.HK")
        self.assertEqual(sanitize_ticker("茅台"), "600519.SS")
        self.assertEqual(sanitize_ticker("贵州茅台 (600519.SS)"), "600519.SS")
        self.assertEqual(sanitize_ticker("IAUM"), "IAUM")

    def test_search_yahoo_tickers_iaum(self):
        results = search_yahoo_tickers("iaum", max_results=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertIn("symbol", top)
        self.assertEqual(top["symbol"], "IAUM")
        self.assertIn("name", top)
        self.assertIn("type", top)
        self.assertIn(top["type"], ["ETF", "Fund", "Equity"])

    def test_get_ticker_metadata(self):
        meta = get_ticker_metadata("IAUM")
        self.assertIsInstance(meta, dict)
        self.assertEqual(meta["symbol"], "IAUM")
        self.assertIn("iShares", meta["name"])
        self.assertEqual(meta["type"], "ETF")

    def test_fetch_realtime_quote(self):
        quote = fetch_realtime_quote("AAPL")
        self.assertIsInstance(quote, dict)
        self.assertEqual(quote.get("status"), "success")
        self.assertEqual(quote.get("ticker"), "AAPL")
        self.assertIn("price", quote)
        self.assertGreater(quote["price"], 0)

if __name__ == "__main__":
    unittest.main()
