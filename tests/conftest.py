"""Shared test configuration.

Force the assistant into deterministic fallback mode for the whole test session so the suite never calls
the Claude API (offline, free, deterministic). The live Claude path is exercised manually / in staging.
"""
import pytest


@pytest.fixture(autouse=True)
def _assistant_offline(settings):
    settings.ASSISTANT_FALLBACK_MODE = True
    settings.ANTHROPIC_API_KEY = ""
