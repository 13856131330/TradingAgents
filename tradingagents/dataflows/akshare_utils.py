"""AKShare data provider for A-share market."""

import re
from datetime import datetime
from typing import Annotated, Optional

import pandas as pd
import akshare as ak


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


def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Get A-share OHLCV data via AKShare.

    Returns CSV string with header, matching yfinance format.
    """
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Normalize ticker
    raw_symbol = symbol
    if is_a_stock_ticker(symbol):
        symbol = normalize_a_stock_ticker(symbol)

    try:
        # AKShare uses YYYYMMDD format
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",  # 前复权
        )

        if df.empty:
            raise AKShareError(f"No data found for symbol '{raw_symbol}' between {start_date} and {end_date}")

        # Rename columns to match yfinance format
        column_mapping = {
            "日期": "Date",
            "股票代码": "Code",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
            "成交额": "Amount",
            "振幅": "Amplitude",
            "涨跌幅": "Change%",
            "涨跌额": "Change",
            "换手率": "Turnover%",
        }
        df = df.rename(columns=column_mapping)

        # Drop redundant Code column (symbol is in the header)
        if "Code" in df.columns:
            df = df.drop(columns=["Code"])

        # Ensure Date column is in the right format
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        # Round numerical values
        numeric_columns = ["Open", "High", "Low", "Close"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].round(2)

        # Convert to CSV string
        csv_string = df.to_csv(index=False)

        # Add header information
        header = f"# Stock data for {raw_symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        raise AKShareError(f"Failed to get stock data for {raw_symbol}: {str(e)}")
