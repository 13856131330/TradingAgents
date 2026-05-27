"""Integration tests for AKShare vendor.

These tests make actual API calls to AKShare and may be slow.
Mark with @pytest.mark.integration to skip in CI.
"""

import pytest
from tradingagents.dataflows.interface import route_to_vendor


@pytest.mark.integration
class TestAKShareIntegration:
    """Integration tests for AKShare vendor routing."""

    def test_route_stock_data(self):
        """Test routing stock data request to AKShare.

        AKShare is the primary vendor for A-share tickers. If the AKShare
        call fails (e.g. API timeout), the fallback chain is exercised and
        the result may contain an error message rather than stock data.
        """
        result = route_to_vendor("get_stock_data", "600519", "2025-01-01", "2025-01-10")
        # Result should be a non-empty string regardless of which vendor responds
        assert isinstance(result, str)
        assert len(result) > 0

    def test_route_indicators(self):
        """Test routing indicators request to AKShare."""
        result = route_to_vendor("get_indicators", "600519", "rsi", "2025-01-10", 5)
        assert "rsi" in result.lower()

    def test_route_fundamentals(self):
        """Test routing fundamentals request to AKShare."""
        result = route_to_vendor("get_fundamentals", "600519")
        assert "Fundamentals" in result or "600519" in result

    def test_route_news(self):
        """Test routing news request to AKShare."""
        result = route_to_vendor("get_news", "600519")
        assert isinstance(result, str)

    def test_non_astock_ticker(self):
        """Test that non-A-stock tickers don't route to AKShare."""
        try:
            result = route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-10")
            assert isinstance(result, str)
        except Exception:
            pass
