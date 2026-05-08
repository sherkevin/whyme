"""Tests for Garden configuration.

Tests:
- get_garden_strong_edge_threshold: Default value and environment variable override
- get_garden_config: Returns complete config dict
"""

import os
from unittest.mock import patch

from agent_os.core.config import get_garden_config, get_garden_strong_edge_threshold


class TestGardenConfig:
    """Test Garden configuration functions."""

    def test_default_threshold(self):
        """Test default threshold is 0.65 when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("GARDEN_STRONG_EDGE_THRESHOLD", None)
            # Force reload by calling function
            threshold = get_garden_strong_edge_threshold()
            assert threshold == 0.65

    def test_custom_threshold(self):
        """Test custom threshold from environment variable."""
        with patch.dict(os.environ, {"GARDEN_STRONG_EDGE_THRESHOLD": "0.8"}):
            threshold = get_garden_strong_edge_threshold()
            assert threshold == 0.8

    def test_threshold_clamped_to_one(self):
        """Test threshold is clamped to max 1.0."""
        with patch.dict(os.environ, {"GARDEN_STRONG_EDGE_THRESHOLD": "1.5"}):
            threshold = get_garden_strong_edge_threshold()
            assert threshold == 1.0

    def test_threshold_clamped_to_zero(self):
        """Test threshold is clamped to min 0.0."""
        with patch.dict(os.environ, {"GARDEN_STRONG_EDGE_THRESHOLD": "-0.5"}):
            threshold = get_garden_strong_edge_threshold()
            assert threshold == 0.0

    def test_invalid_threshold_fallback(self):
        """Test invalid threshold falls back to default."""
        with patch.dict(os.environ, {"GARDEN_STRONG_EDGE_THRESHOLD": "invalid"}):
            threshold = get_garden_strong_edge_threshold()
            assert threshold == 0.65

    def test_get_garden_config(self):
        """Test get_garden_config returns complete config dict."""
        with patch.dict(os.environ, {"GARDEN_STRONG_EDGE_THRESHOLD": "0.75"}):
            config = get_garden_config()
            assert isinstance(config, dict)
            assert "strong_edge_threshold" in config
            assert config["strong_edge_threshold"] == 0.75
