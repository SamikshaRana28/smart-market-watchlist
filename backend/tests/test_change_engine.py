# """Worked examples for the Attention Score engine.

# Run from the backend folder:
#     python -m unittest tests.test_change_engine
# """

# from __future__ import annotations

# import unittest

# from app.core.change_engine import (
#     PRICE_RETURN_CAP,
#     PRICE_WEIGHT,
#     RATIO_CAP,
#     RATIO_NORMAL,
#     VOLUME_WEIGHT,
#     VOLATILITY_WEIGHT,
#     Z_SCORE_CAP,
#     Z_SCORE_WEIGHT,
#     calculate_attention_score,
#     calculate_return,
#     calculate_sector_correlation,
#     calculate_volatility_ratio,
#     calculate_volume_ratio,
#     calculate_z_score,
#     classify_attention,
# )


# class TestCalculateReturn(unittest.TestCase):
#     def test_ten_percent_up(self) -> None:
#         # (110 - 100) / 100 = 0.10
#         self.assertAlmostEqual(calculate_return(110, 100), 0.10)

#     def test_five_percent_down(self) -> None:
#         # (95 - 100) / 100 = -0.05
#         self.assertAlmostEqual(calculate_return(95, 100), -0.05)

#     def test_zero_previous_price_returns_none(self) -> None:
#         self.assertIsNone(calculate_return(10, 0))


# class TestCalculateZScore(unittest.TestCase):
#     def test_two_sigma_move(self) -> None:
#         # (0.05 - 0.01) / 0.02 = 2.0
#         self.assertAlmostEqual(calculate_z_score(0.05, 0.01, 0.02), 2.0)

#     def test_negative_z(self) -> None:
#         # (0.00 - 0.02) / 0.01 = -2.0
#         self.assertAlmostEqual(calculate_z_score(0.00, 0.02, 0.01), -2.0)

#     def test_zero_sigma_matching_mean(self) -> None:
#         self.assertEqual(calculate_z_score(0.01, 0.01, 0.0), 0.0)

#     def test_zero_sigma_unexpected_move(self) -> None:
#         self.assertEqual(calculate_z_score(0.05, 0.01, 0.0), Z_SCORE_CAP)


# class TestCalculateVolumeRatio(unittest.TestCase):
#     def test_double_average_volume(self) -> None:
#         # 2_000_000 / 1_000_000 = 2.0
#         self.assertAlmostEqual(calculate_volume_ratio(2_000_000, 1_000_000), 2.0)

#     def test_zero_average_returns_none(self) -> None:
#         self.assertIsNone(calculate_volume_ratio(500, 0))


# class TestCalculateVolatilityRatio(unittest.TestCase):
#     def test_one_and_a_half_times_normal(self) -> None:
#         # 0.03 / 0.02 = 1.5
#         self.assertAlmostEqual(calculate_volatility_ratio(0.03, 0.02), 1.5)

#     def test_zero_baseline_returns_none(self) -> None:
#         self.assertIsNone(calculate_volatility_ratio(0.02, 0))


# class TestCalculateAttentionScore(unittest.TestCase):
#     def test_worked_example(self) -> None:
#         """Hand-computed mix used as the reference for judges.

#         return = 0.05  → price_score = |0.05| / 0.10 * 100 = 50
#         z      = 2.0   → z_norm      = |2.0| / 3.0 * 100  = 66.666...
#         vol    = 2.0   → volume      = (2-1) / (3-1) * 100 = 50
#         volat  = 1.5   → volatility  = (1.5-1) / (3-1) * 100 = 25

#         score = 0.35*50 + 0.30*(200/3) + 0.20*50 + 0.15*25
#               = 17.5 + 20 + 10 + 3.75
#               = 51.25
#         """
#         result = calculate_attention_score(
#             price_return=0.05,
#             z_score=2.0,
#             volume_ratio=2.0,
#             volatility_ratio=1.5,
#         )

#         expected_price = abs(0.05) / PRICE_RETURN_CAP * 100
#         expected_z = abs(2.0) / Z_SCORE_CAP * 100
#         expected_vol = (2.0 - RATIO_NORMAL) / (RATIO_CAP - RATIO_NORMAL) * 100
#         expected_volat = (1.5 - RATIO_NORMAL) / (RATIO_CAP - RATIO_NORMAL) * 100
#         expected_score = (
#             PRICE_WEIGHT * expected_price
#             + Z_SCORE_WEIGHT * expected_z
#             + VOLUME_WEIGHT * expected_vol
#             + VOLATILITY_WEIGHT * expected_volat
#         )

#         self.assertAlmostEqual(result["price_score"], 50.0)
#         self.assertAlmostEqual(result["z_score_normalized"], round(expected_z, 4))
#         self.assertAlmostEqual(result["volume_score"], 50.0)
#         self.assertAlmostEqual(result["volatility_score"], 25.0)
#         self.assertAlmostEqual(result["attention_score"], round(expected_score, 4))
#         self.assertAlmostEqual(result["attention_score"], 51.25)

#     def test_down_move_scores_same_as_up_move(self) -> None:
#         up = calculate_attention_score(0.08, 2.5, 1.0, 1.0)
#         down = calculate_attention_score(-0.08, -2.5, 1.0, 1.0)
#         self.assertEqual(up["price_score"], down["price_score"])
#         self.assertEqual(up["z_score_normalized"], down["z_score_normalized"])
#         self.assertEqual(up["attention_score"], down["attention_score"])

#     def test_normal_volume_and_vol_score_zero(self) -> None:
#         result = calculate_attention_score(0.0, 0.0, 1.0, 1.0)
#         self.assertEqual(result["volume_score"], 0.0)
#         self.assertEqual(result["volatility_score"], 0.0)
#         self.assertEqual(result["attention_score"], 0.0)

#     def test_missing_ratios_do_not_crash(self) -> None:
#         result = calculate_attention_score(0.10, 3.0, None, None)
#         self.assertEqual(result["volume_score"], 0.0)
#         self.assertEqual(result["volatility_score"], 0.0)
#         self.assertGreater(result["attention_score"], 0.0)


# class TestClassifyAttention(unittest.TestCase):
#     def test_buckets(self) -> None:
#         self.assertEqual(classify_attention(0), "normal")
#         self.assertEqual(classify_attention(29.9), "normal")
#         self.assertEqual(classify_attention(30), "moderate")
#         self.assertEqual(classify_attention(51.25), "moderate")
#         self.assertEqual(classify_attention(59.9), "moderate")
#         self.assertEqual(classify_attention(60), "important")
#         self.assertEqual(classify_attention(79.9), "important")
#         self.assertEqual(classify_attention(80), "significant")
#         self.assertEqual(classify_attention(100), "significant")


# class TestCalculateSectorCorrelation(unittest.TestCase):
#     def test_two_tech_names_unusual_same_day(self) -> None:
#         flags = calculate_sector_correlation(
#             [
#                 {"symbol": "AAPL", "sector": "Technology", "z_score": 2.1},
#                 {"symbol": "MSFT", "sector": "Technology", "z_score": -1.8},
#                 {"symbol": "JPM", "sector": "Financials", "z_score": 0.4},
#             ]
#         )
#         self.assertEqual(flags["AAPL"], "sector_correlation")
#         self.assertEqual(flags["MSFT"], "sector_correlation")
#         self.assertEqual(flags["JPM"], "stock_specific")

#     def test_lone_outlier_stays_stock_specific(self) -> None:
#         flags = calculate_sector_correlation(
#             [
#                 {"symbol": "NVDA", "sector": "Technology", "z_score": 2.8},
#                 {"symbol": "AAPL", "sector": "Technology", "z_score": 0.3},
#                 {"symbol": "XOM", "sector": "Energy", "z_score": 2.0},
#             ]
#         )
#         self.assertEqual(flags["NVDA"], "stock_specific")
#         self.assertEqual(flags["AAPL"], "stock_specific")
#         self.assertEqual(flags["XOM"], "stock_specific")

#     def test_below_threshold_not_counted(self) -> None:
#         flags = calculate_sector_correlation(
#             [
#                 {"symbol": "AAPL", "sector": "Technology", "z_score": 1.5},
#                 {"symbol": "MSFT", "sector": "Technology", "z_score": 1.5},
#             ]
#         )
#         # spec is |z| > 1.5, not >=
#         self.assertEqual(flags["AAPL"], "stock_specific")
#         self.assertEqual(flags["MSFT"], "stock_specific")


# if __name__ == "__main__":
#     unittest.main()


"""Worked examples for the Attention Score engine.

Run from the backend folder:
    python -m unittest tests.test_change_engine
"""

from __future__ import annotations

import unittest

from app.core.change_engine import (
    PRICE_RETURN_CAP,
    PRICE_WEIGHT,
    RATIO_CAP,
    RATIO_NORMAL,
    SENSITIVITY_PRESETS,
    VOLUME_WEIGHT,
    VOLATILITY_WEIGHT,
    Z_SCORE_CAP,
    Z_SCORE_WEIGHT,
    calculate_attention_score,
    calculate_return,
    calculate_sector_correlation,
    calculate_volatility_ratio,
    calculate_volume_ratio,
    calculate_z_score,
    classify_attention,
)


class TestCalculateReturn(unittest.TestCase):
    def test_ten_percent_up(self) -> None:
        # (110 - 100) / 100 = 0.10
        self.assertAlmostEqual(calculate_return(110, 100), 0.10)

    def test_five_percent_down(self) -> None:
        # (95 - 100) / 100 = -0.05
        self.assertAlmostEqual(calculate_return(95, 100), -0.05)

    def test_zero_previous_price_returns_none(self) -> None:
        self.assertIsNone(calculate_return(10, 0))


class TestCalculateZScore(unittest.TestCase):
    def test_two_sigma_move(self) -> None:
        # (0.05 - 0.01) / 0.02 = 2.0
        self.assertAlmostEqual(calculate_z_score(0.05, 0.01, 0.02), 2.0)

    def test_negative_z(self) -> None:
        # (0.00 - 0.02) / 0.01 = -2.0
        self.assertAlmostEqual(calculate_z_score(0.00, 0.02, 0.01), -2.0)

    def test_zero_sigma_matching_mean(self) -> None:
        self.assertEqual(calculate_z_score(0.01, 0.01, 0.0), 0.0)

    def test_zero_sigma_unexpected_move(self) -> None:
        self.assertEqual(calculate_z_score(0.05, 0.01, 0.0), Z_SCORE_CAP)


class TestCalculateVolumeRatio(unittest.TestCase):
    def test_double_average_volume(self) -> None:
        # 2_000_000 / 1_000_000 = 2.0
        self.assertAlmostEqual(calculate_volume_ratio(2_000_000, 1_000_000), 2.0)

    def test_zero_average_returns_none(self) -> None:
        self.assertIsNone(calculate_volume_ratio(500, 0))


class TestCalculateVolatilityRatio(unittest.TestCase):
    def test_one_and_a_half_times_normal(self) -> None:
        # 0.03 / 0.02 = 1.5
        self.assertAlmostEqual(calculate_volatility_ratio(0.03, 0.02), 1.5)

    def test_zero_baseline_returns_none(self) -> None:
        self.assertIsNone(calculate_volatility_ratio(0.02, 0))


class TestCalculateAttentionScore(unittest.TestCase):
    def test_worked_example(self) -> None:
        """Hand-computed mix used as the reference for judges.

        return = 0.05  → price_score = |0.05| / 0.10 * 100 = 50
        z      = 2.0   → z_norm      = |2.0| / 3.0 * 100  = 66.666...
        vol    = 2.0   → volume      = (2-1) / (3-1) * 100 = 50
        volat  = 1.5   → volatility  = (1.5-1) / (3-1) * 100 = 25

        score = 0.35*50 + 0.30*(200/3) + 0.20*50 + 0.15*25
              = 17.5 + 20 + 10 + 3.75
              = 51.25
        """
        result = calculate_attention_score(
            price_return=0.05,
            z_score=2.0,
            volume_ratio=2.0,
            volatility_ratio=1.5,
        )

        expected_price = abs(0.05) / PRICE_RETURN_CAP * 100
        expected_z = abs(2.0) / Z_SCORE_CAP * 100
        expected_vol = (2.0 - RATIO_NORMAL) / (RATIO_CAP - RATIO_NORMAL) * 100
        expected_volat = (1.5 - RATIO_NORMAL) / (RATIO_CAP - RATIO_NORMAL) * 100
        expected_score = (
            PRICE_WEIGHT * expected_price
            + Z_SCORE_WEIGHT * expected_z
            + VOLUME_WEIGHT * expected_vol
            + VOLATILITY_WEIGHT * expected_volat
        )

        self.assertAlmostEqual(result["price_score"], 50.0)
        self.assertAlmostEqual(result["z_score_normalized"], round(expected_z, 4))
        self.assertAlmostEqual(result["volume_score"], 50.0)
        self.assertAlmostEqual(result["volatility_score"], 25.0)
        self.assertAlmostEqual(result["attention_score"], round(expected_score, 4))
        self.assertAlmostEqual(result["attention_score"], 51.25)

    def test_down_move_scores_same_as_up_move(self) -> None:
        up = calculate_attention_score(0.08, 2.5, 1.0, 1.0)
        down = calculate_attention_score(-0.08, -2.5, 1.0, 1.0)
        self.assertEqual(up["price_score"], down["price_score"])
        self.assertEqual(up["z_score_normalized"], down["z_score_normalized"])
        self.assertEqual(up["attention_score"], down["attention_score"])

    def test_normal_volume_and_vol_score_zero(self) -> None:
        result = calculate_attention_score(0.0, 0.0, 1.0, 1.0)
        self.assertEqual(result["volume_score"], 0.0)
        self.assertEqual(result["volatility_score"], 0.0)
        self.assertEqual(result["attention_score"], 0.0)

    def test_missing_ratios_do_not_crash(self) -> None:
        result = calculate_attention_score(0.10, 3.0, None, None)
        self.assertEqual(result["volume_score"], 0.0)
        self.assertEqual(result["volatility_score"], 0.0)
        self.assertGreater(result["attention_score"], 0.0)


class TestClassifyAttention(unittest.TestCase):
    def test_buckets(self) -> None:
        self.assertEqual(classify_attention(0), "normal")
        self.assertEqual(classify_attention(29.9), "normal")
        self.assertEqual(classify_attention(30), "moderate")
        self.assertEqual(classify_attention(51.25), "moderate")
        self.assertEqual(classify_attention(59.9), "moderate")
        self.assertEqual(classify_attention(60), "important")
        self.assertEqual(classify_attention(79.9), "important")
        self.assertEqual(classify_attention(80), "significant")
        self.assertEqual(classify_attention(100), "significant")

    def test_same_score_classifies_differently_across_presets(self) -> None:
        # A score of 50 is "moderate" under Balanced and Conservative, but
        # "important" under Aggressive (its important cutoff is 45, not 60) —
        # proves the thresholds param actually shifts behavior, not just the
        # score math.
        score = 50.0
        self.assertEqual(
            classify_attention(score, SENSITIVITY_PRESETS["balanced"]), "moderate"
        )
        self.assertEqual(
            classify_attention(score, SENSITIVITY_PRESETS["aggressive"]), "important"
        )

        # A score of 35 is "normal" under Conservative (needs 40+ to even be
        # moderate) but "moderate" under Balanced — same score, different verdict.
        low_score = 35.0
        self.assertEqual(
            classify_attention(low_score, SENSITIVITY_PRESETS["conservative"]), "normal"
        )
        self.assertEqual(
            classify_attention(low_score, SENSITIVITY_PRESETS["balanced"]), "moderate"
        )

    def test_default_thresholds_unchanged_when_no_preset_given(self) -> None:
        # No thresholds arg passed -> must still match the original 30/60/80 buckets.
        self.assertEqual(classify_attention(29.9), "normal")
        self.assertEqual(classify_attention(30), "moderate")


class TestCalculateSectorCorrelation(unittest.TestCase):
    def test_two_tech_names_unusual_same_day(self) -> None:
        flags = calculate_sector_correlation(
            [
                {"symbol": "AAPL", "sector": "Technology", "z_score": 2.1},
                {"symbol": "MSFT", "sector": "Technology", "z_score": -1.8},
                {"symbol": "JPM", "sector": "Financials", "z_score": 0.4},
            ]
        )
        self.assertEqual(flags["AAPL"], "sector_correlation")
        self.assertEqual(flags["MSFT"], "sector_correlation")
        self.assertEqual(flags["JPM"], "stock_specific")

    def test_lone_outlier_stays_stock_specific(self) -> None:
        flags = calculate_sector_correlation(
            [
                {"symbol": "NVDA", "sector": "Technology", "z_score": 2.8},
                {"symbol": "AAPL", "sector": "Technology", "z_score": 0.3},
                {"symbol": "XOM", "sector": "Energy", "z_score": 2.0},
            ]
        )
        self.assertEqual(flags["NVDA"], "stock_specific")
        self.assertEqual(flags["AAPL"], "stock_specific")
        self.assertEqual(flags["XOM"], "stock_specific")

    def test_below_threshold_not_counted(self) -> None:
        flags = calculate_sector_correlation(
            [
                {"symbol": "AAPL", "sector": "Technology", "z_score": 1.5},
                {"symbol": "MSFT", "sector": "Technology", "z_score": 1.5},
            ]
        )
        # spec is |z| > 1.5, not >=
        self.assertEqual(flags["AAPL"], "stock_specific")
        self.assertEqual(flags["MSFT"], "stock_specific")


if __name__ == "__main__":
    unittest.main()
