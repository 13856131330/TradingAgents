"""Tests for AKShare vendor utility functions."""

import pytest
from tradingagents.dataflows.akshare_utils import (
    is_a_stock_ticker,
    normalize_a_stock_ticker,
)


class TestIsAStockTicker:
    """Test A-share ticker detection."""

    def test_pure_6digit(self):
        assert is_a_stock_ticker("600519") is True
        assert is_a_stock_ticker("000001") is True
        assert is_a_stock_ticker("300750") is True

    def test_with_suffix(self):
        assert is_a_stock_ticker("600519.SH") is True
        assert is_a_stock_ticker("000001.SZ") is True
        assert is_a_stock_ticker("600519.sh") is True

    def test_with_prefix(self):
        assert is_a_stock_ticker("sh600519") is True
        assert is_a_stock_ticker("sz000001") is True
        assert is_a_stock_ticker("SH600519") is True

    def test_us_tickers(self):
        assert is_a_stock_ticker("AAPL") is False
        assert is_a_stock_ticker("MSFT") is False
        assert is_a_stock_ticker("GOOGL") is False

    def test_edge_cases(self):
        assert is_a_stock_ticker("") is False
        assert is_a_stock_ticker(None) is False
        assert is_a_stock_ticker("12345") is False  # 5 digits
        assert is_a_stock_ticker("1234567") is False  # 7 digits


class TestNormalizeAStockTicker:
    """Test A-share ticker normalization."""

    def test_pure_6digit(self):
        assert normalize_a_stock_ticker("600519") == "600519"

    def test_remove_suffix(self):
        assert normalize_a_stock_ticker("600519.SH") == "600519"
        assert normalize_a_stock_ticker("000001.SZ") == "000001"

    def test_remove_prefix(self):
        assert normalize_a_stock_ticker("sh600519") == "600519"
        assert normalize_a_stock_ticker("sz000001") == "000001"

    def test_whitespace(self):
        assert normalize_a_stock_ticker("  600519  ") == "600519"


class TestGetStockData:
    """Test OHLCV data fetching."""

    def test_basic_fetch(self):
        """Test fetching stock data for a known A-share."""
        from tradingagents.dataflows.akshare_utils import get_stock_data
        result = get_stock_data("600519", "2025-01-01", "2025-01-10")
        assert "Stock data for 600519" in result
        assert "Date,Open,Close,High,Low" in result or "日期,开盘,收盘" in result

    def test_with_prefix(self):
        """Test fetching with sh/sz prefix."""
        from tradingagents.dataflows.akshare_utils import get_stock_data
        result = get_stock_data("sh600519", "2025-01-01", "2025-01-10")
        assert "600519" in result

    def test_invalid_ticker(self):
        """Test error handling for invalid ticker."""
        from tradingagents.dataflows.akshare_utils import get_stock_data, AKShareError
        with pytest.raises(AKShareError):
            get_stock_data("999999", "2025-01-01", "2025-01-10")


class TestGetIndicators:
    """Test technical indicator calculation."""

    def test_rsi_indicator(self):
        """Test RSI calculation."""
        from tradingagents.dataflows.akshare_utils import get_indicators
        result = get_indicators("600519", "rsi", "2025-01-10", 5)
        assert "rsi" in result.lower()

    def test_macd_indicator(self):
        """Test MACD calculation."""
        from tradingagents.dataflows.akshare_utils import get_indicators
        result = get_indicators("600519", "macd", "2025-01-10", 5)
        assert "macd" in result.lower()

    def test_invalid_indicator(self):
        """Test error for unsupported indicator."""
        from tradingagents.dataflows.akshare_utils import get_indicators
        with pytest.raises(ValueError, match="not supported"):
            get_indicators("600519", "invalid_indicator", "2025-01-10", 5)


class TestGetFundamentals:
    """Test fundamentals data fetching."""

    def test_basic_fundamentals(self):
        """Test fetching fundamentals for a known A-share."""
        from tradingagents.dataflows.akshare_utils import get_fundamentals
        result = get_fundamentals("600519")
        assert "Company Fundamentals" in result
        assert "600519" in result

    def test_balance_sheet(self):
        """Test fetching balance sheet."""
        from tradingagents.dataflows.akshare_utils import get_balance_sheet
        result = get_balance_sheet("600519")
        assert "Balance Sheet" in result

    def test_cashflow(self):
        """Test fetching cash flow."""
        from tradingagents.dataflows.akshare_utils import get_cashflow
        result = get_cashflow("600519")
        assert "Cash Flow" in result

    def test_income_statement(self):
        """Test fetching income statement."""
        from tradingagents.dataflows.akshare_utils import get_income_statement
        result = get_income_statement("600519")
        assert "Income Statement" in result
