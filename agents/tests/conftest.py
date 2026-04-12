"""Shared test fixtures."""

import pytest

from src.application.config import AppConfig


@pytest.fixture()
def fred_api_key() -> str:
    """Return the FRED API key from config, or skip if not set."""
    config = AppConfig()
    if not config.fred_api_key:
        pytest.skip("FRED API key not configured")
    return config.fred_api_key
