"""Sensitivity query-param -> threshold preset mapping for GET /watchlists/{id}/changes."""

from __future__ import annotations

import unittest

from app.core.change_engine import DEFAULT_THRESHOLDS, SENSITIVITY_PRESETS
from app.routes.watchlists import _thresholds_for


class TestThresholdsFor(unittest.TestCase):
    def test_valid_values_map_to_their_preset(self) -> None:
        self.assertEqual(_thresholds_for("conservative"), SENSITIVITY_PRESETS["conservative"])
        self.assertEqual(_thresholds_for("balanced"), SENSITIVITY_PRESETS["balanced"])
        self.assertEqual(_thresholds_for("aggressive"), SENSITIVITY_PRESETS["aggressive"])

    def test_case_and_whitespace_insensitive(self) -> None:
        self.assertEqual(_thresholds_for("  Aggressive  "), SENSITIVITY_PRESETS["aggressive"])
        self.assertEqual(_thresholds_for("CONSERVATIVE"), SENSITIVITY_PRESETS["conservative"])

    def test_missing_or_invalid_falls_back_to_balanced_default(self) -> None:
        self.assertEqual(_thresholds_for(None), DEFAULT_THRESHOLDS)
        self.assertEqual(_thresholds_for(""), DEFAULT_THRESHOLDS)
        self.assertEqual(_thresholds_for("yolo-mode"), DEFAULT_THRESHOLDS)


if __name__ == "__main__":
    unittest.main()
