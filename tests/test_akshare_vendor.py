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
