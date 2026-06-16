import unittest
from sentiment.functions.utils.formulas import (
    calculate_raw_sentiment,
    calculate_macro_surprise,
    calculate_effective_sentiment,
    calculate_portfolio_sentiment,
    calculate_portfolio_drift
)

class TestFormulas(unittest.TestCase):
    
    def test_calculate_raw_sentiment(self):
        # Case 1: Empty list
        self.assertEqual(calculate_raw_sentiment([]), 0.0)
        self.assertEqual(calculate_raw_sentiment(None), 0.0)
        
        # Case 2: Normal calculation
        articles = [
            {"sentiment_score": 0.80, "confidence": 0.90},
            {"sentiment_score": -0.60, "confidence": 0.85}
        ]
        # (0.8*0.9 + -0.6*0.85) / (0.9 + 0.85) = (0.72 - 0.51) / 1.75 = 0.21 / 1.75 = 0.12
        self.assertAlmostEqual(calculate_raw_sentiment(articles), 0.12, places=4)
        
        # Case 3: Sum of confidences is 0
        zero_conf = [{"sentiment_score": 0.50, "confidence": 0.0}]
        self.assertEqual(calculate_raw_sentiment(zero_conf), 0.0)
        
        # Case 4: Skip malformed dictionary entries
        malformed = [
            {"sentiment_score": 0.80, "confidence": 0.90},
            {"sentiment_score": None, "confidence": 0.85},
            {"sentiment_score": -0.60, "confidence": None}
        ]
        self.assertAlmostEqual(calculate_raw_sentiment(malformed), 0.80, places=4)

    def test_calculate_macro_surprise(self):
        # Case 1: Red tier event (weight 1.0)
        actual = 3.5
        consensus = 2.0
        historical_std = 0.5
        val, warning = calculate_macro_surprise(actual, consensus, historical_std, "red")
        # 1.0 * |(3.5 - 2.0) / 0.5| = 3.0
        self.assertEqual(val, 3.0)
        self.assertFalse(warning)
        
        # Case 2: Orange tier event (weight 0.5)
        actual = 1.5
        consensus = 2.0
        historical_std = 0.5
        val, warning = calculate_macro_surprise(actual, consensus, historical_std, "orange")
        # 0.5 * |(1.5 - 2.0) / 0.5| = 0.5
        self.assertEqual(val, 0.5)
        self.assertFalse(warning)
        
        # Case 3: Fallback division by zero std (<=0)
        actual = 3.0
        consensus = 2.0
        historical_std = 0.0
        val, warning = calculate_macro_surprise(actual, consensus, historical_std, "red")
        # 1.0 * |(3.0 - 2.0) / 1.0| = 1.0
        self.assertEqual(val, 1.0)
        self.assertTrue(warning)

    def test_calculate_effective_sentiment(self):
        # Case 1: Default beta lookup for AAPL (beta 1.2)
        raw_sentiment = 0.5
        macro_shock = 2.0
        val = calculate_effective_sentiment("AAPL", raw_sentiment, macro_shock)
        # 0.5 * (1 + 1.2 * 2.0) = 1.7
        self.assertAlmostEqual(val, 1.7, places=4)
        
        # Case 2: Custom beta overrides default (custom_beta 1.5)
        val = calculate_effective_sentiment("AAPL", raw_sentiment, macro_shock, custom_beta=1.5)
        # 0.5 * (1 + 1.5 * 2.0) = 2.0
        self.assertAlmostEqual(val, 2.0, places=4)
        
        # Case 3: Default fallback lookup for unknown ticker (beta 1.0)
        val = calculate_effective_sentiment("XYZ", raw_sentiment, macro_shock)
        # 0.5 * (1 + 1.0 * 2.0) = 1.5
        self.assertAlmostEqual(val, 1.5, places=4)

    def test_calculate_portfolio_sentiment(self):
        # Case 1: Standard weights and sentiments
        weights = {"AAPL": 0.40, "MSFT": 0.60}
        sentiments = {"AAPL": 1.5, "MSFT": -0.5}
        val = calculate_portfolio_sentiment(weights, sentiments)
        # 0.40 * 1.5 + 0.60 * (-0.5) = 0.30
        self.assertAlmostEqual(val, 0.30, places=4)
        
        # Case 2: Missing ticker in sentiments defaults to 0.0
        sentiments_missing = {"AAPL": 1.5}
        val = calculate_portfolio_sentiment(weights, sentiments_missing)
        # 0.40 * 1.5 + 0.60 * 0.0 = 0.60
        self.assertAlmostEqual(val, 0.60, places=4)
        
        # Case 3: Empty inputs
        self.assertEqual(calculate_portfolio_sentiment({}, {}), 0.0)

    def test_calculate_portfolio_drift(self):
        # Case 1: Clean overlap L1 drift
        actual = {"AAPL": 0.40, "MSFT": 0.60}
        target = {"AAPL": 0.35, "MSFT": 0.65}
        val = calculate_portfolio_drift(actual, target)
        # |0.40 - 0.35| + |0.60 - 0.65| = 0.05 + 0.05 = 0.10
        self.assertAlmostEqual(val, 0.10, places=4)
        
        # Case 2: Non-overlapping tickers
        target_missing = {"AAPL": 1.00}
        val = calculate_portfolio_drift(actual, target_missing)
        # |0.40 - 1.00| + |0.60 - 0.00| = 0.60 + 0.60 = 1.20
        self.assertAlmostEqual(val, 1.20, places=4)


if __name__ == "__main__":
    unittest.main()
