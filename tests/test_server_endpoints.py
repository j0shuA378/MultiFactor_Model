import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

class TestServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_fundamentals_endpoint_aapl(self):
        res = self.client.get('/api/stock/fundamentals?ticker=AAPL')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("profile", data)
        self.assertEqual(data["profile"]["symbol"], "AAPL")
        self.assertIn("valuation", data)
        self.assertIn("financials", data)
        self.assertIn("analyst", data)
        self.assertIn("dividends", data)
        self.assertIn("target_mean_price", data["analyst"])

    def test_fundamentals_endpoint_fallback(self):
        res = self.client.get('/api/stock/fundamentals?ticker=600519.SS')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data["profile"]["symbol"], "600519.SS")

    def test_screener_endpoint_categories(self):
        for cat in ["all", "us_tech", "etf_gold", "china_hk", "a_shares", "high_dividend"]:
            res = self.client.get(f'/api/screener?category={cat}')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data.get("status"), "success")
            self.assertEqual(data.get("category"), cat)
            self.assertGreater(data.get("count", 0), 0)
            self.assertIsInstance(data.get("stocks"), list)

if __name__ == "__main__":
    unittest.main()
