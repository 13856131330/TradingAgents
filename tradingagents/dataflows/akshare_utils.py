"""AKShare data provider for A-share market."""

import re
from typing import Optional


class AKShareError(Exception):
    """AKShare API call error."""
    pass


def is_a_stock_ticker(ticker: str) -> bool:
    """Check if ticker is an A-share stock code.

    Supports formats:
    - Pure 6-digit: 600519
    - With suffix: 600519.SH, 600519.SZ
    - With prefix: sh600519, sz600519
    """
    if not ticker:
        return False
    ticker = ticker.strip()
    # Pure 6-digit
    if re.match(r'^\d{6}$', ticker):
        return True
    # With .SH/.SZ suffix
    if re.match(r'^\d{6}\.(SH|SZ)$', ticker.upper()):
        return True
    # With sh/sz prefix
    if re.match(r'^(sh|sz)\d{6}$', ticker.lower()):
        return True
    return False


def normalize_a_stock_ticker(ticker: str) -> str:
    """Convert A-share ticker to pure 6-digit format for AKShare.

    Examples:
    - 600519 -> 600519
    - 600519.SH -> 600519
    - sh600519 -> 600519
    """
    ticker = ticker.strip()
    # Remove .SH/.SZ suffix
    if '.' in ticker:
        ticker = ticker.split('.')[0]
    # Remove sh/sz prefix
    if ticker.lower().startswith(('sh', 'sz')):
        ticker = ticker[2:]
    return ticker
