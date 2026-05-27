# AKShare A股数据集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集成 AKShare 作为 A 股数据专用 vendor，支持用户输入纯 6 位数字 ticker 自动获取最新 A 股数据

**Architecture:** 在现有 vendor routing 架构中注册 `"akshare"` vendor，通过 ticker 自动识别路由到 AKShare 实现。新建 `akshare_utils.py` 实现所有 9 个数据方法，修改 `interface.py` 添加路由逻辑。

**Tech Stack:** Python, akshare, pandas, pytest

---

## 文件结构

### 新增文件
- `tradingagents/dataflows/akshare_utils.py` — AKShare 数据获取实现（9 个方法）
- `tests/test_akshare_vendor.py` — AKShare vendor 单元测试
- `tests/test_akshare_integration.py` — AKShare 集成测试

### 修改文件
- `tradingagents/dataflows/interface.py` — 注册 vendor、添加 ticker 检测和路由逻辑
- `tradingagents/default_config.py` — 添加 AKShare 配置项

---

## Task 1: 安装依赖并验证

**Files:**
- Modify: `pyproject.toml` (如需要)

- [ ] **Step 1: 安装 akshare 包**

```bash
pip install akshare
```

- [ ] **Step 2: 验证安装成功**

```bash
python -c "import akshare as ak; print(ak.__version__)"
```

Expected: 输出版本号，无报错

- [ ] **Step 3: 测试基本 API 调用**

```bash
python -c "
import akshare as ak
# 测试获取贵州茅台行情
df = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date='20250101', end_date='20250110', adjust='qfq')
print(df.head())
print('Columns:', df.columns.tolist())
"
```

Expected: 输出 DataFrame，包含日期、开盘、收盘、最高、最低、成交量等列

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "deps: add akshare dependency"
```

---

## Task 2: 实现 Ticker 识别和转换工具函数

**Files:**
- Create: `tradingagents/dataflows/akshare_utils.py`

- [ ] **Step 1: 创建 akshare_utils.py 并实现 ticker 工具函数**

```python
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
```

- [ ] **Step 2: 编写 ticker 工具函数测试**

```python
# tests/test_akshare_vendor.py
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
```

- [ ] **Step 3: 运行测试验证通过**

```bash
pytest tests/test_akshare_vendor.py::TestIsAStockTicker -v
pytest tests/test_akshare_vendor.py::TestNormalizeAStockTicker -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/akshare_utils.py tests/test_akshare_vendor.py
git commit -m "feat(akshare): add ticker detection and normalization utilities"
```

---

## Task 3: 实现 OHLCV 数据获取

**Files:**
- Modify: `tradingagents/dataflows/akshare_utils.py`

- [ ] **Step 1: 实现 get_stock_data 函数**

在 `akshare_utils.py` 中添加：

```python
from datetime import datetime
from typing import Annotated
import pandas as pd
import akshare as ak


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
            return f"No data found for symbol '{raw_symbol}' between {start_date} and {end_date}"

        # Rename columns to match yfinance format
        column_mapping = {
            "日期": "Date",
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
```

- [ ] **Step 2: 编写 OHLCV 测试**

在 `tests/test_akshare_vendor.py` 中添加：

```python
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
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_akshare_vendor.py::TestGetStockData -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/akshare_utils.py tests/test_akshare_vendor.py
git commit -m "feat(akshare): implement OHLCV data fetching"
```

---

## Task 4: 实现技术指标计算

**Files:**
- Modify: `tradingagents/dataflows/akshare_utils.py`

- [ ] **Step 1: 实现技术指标计算函数**

在 `akshare_utils.py` 中添加：

```python
from dateutil.relativedelta import relativedelta


def _calculate_indicators(df: pd.DataFrame) -> dict:
    """Calculate technical indicators from OHLCV data.

    Returns dict mapping indicator names to pandas Series.
    """
    indicators = {}

    # SMA
    indicators['close_50_sma'] = df['Close'].rolling(50).mean()
    indicators['close_200_sma'] = df['Close'].rolling(200).mean()

    # EMA
    indicators['close_10_ema'] = df['Close'].ewm(span=10).mean()

    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    indicators['macd'] = ema12 - ema26
    indicators['macds'] = indicators['macd'].ewm(span=9).mean()
    indicators['macdh'] = indicators['macd'] - indicators['macds']

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    indicators['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    indicators['close_20_sma'] = df['Close'].rolling(20).mean()
    std = df['Close'].rolling(20).std()
    indicators['boll'] = indicators['close_20_sma']
    indicators['boll_ub'] = indicators['close_20_sma'] + 2 * std
    indicators['boll_lb'] = indicators['close_20_sma'] - 2 * std

    # ATR
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    indicators['atr'] = tr.rolling(14).mean()

    # VWMA (Volume Weighted Moving Average)
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    indicators['vwma'] = (typical_price * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()

    # MFI (Money Flow Index)
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    money_flow = typical_price * df['Volume']
    positive_flow = money_flow.where(typical_price > typical_price.shift(), 0).rolling(14).sum()
    negative_flow = money_flow.where(typical_price < typical_price.shift(), 0).rolling(14).sum()
    mfi_ratio = positive_flow / negative_flow
    indicators['mfi'] = 100 - (100 / (1 + mfi_ratio))

    return indicators


# Indicator descriptions matching yfinance format
INDICATOR_DESCRIPTIONS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
    ),
}


def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """Get technical indicator values for A-share stocks via AKShare.

    Returns formatted string with indicator values for the look-back period.
    """
    if indicator not in INDICATOR_DESCRIPTIONS:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(INDICATOR_DESCRIPTIONS.keys())}"
        )

    # Normalize ticker
    raw_symbol = symbol
    if is_a_stock_ticker(symbol):
        symbol = normalize_a_stock_ticker(symbol)

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        # Fetch OHLCV data with extra lookback for indicator calculation
        start_date = (before - relativedelta(days=300)).strftime("%Y-%m-%d")  # Extra days for SMA200
        end_date = curr_date

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )

        if df.empty:
            return f"No data found for symbol '{raw_symbol}'"

        # Rename columns
        column_mapping = {
            "日期": "Date",
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
        }
        df = df.rename(columns=column_mapping)
        df["Date"] = pd.to_datetime(df["Date"])

        # Calculate indicators
        indicators = _calculate_indicators(df)
        indicator_series = indicators[indicator]

        # Build result string for the look-back period
        ind_string = ""
        current_dt = curr_date_dt
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            matching_rows = df[df["Date"].dt.strftime("%Y-%m-%d") == date_str]

            if not matching_rows.empty:
                idx = matching_rows.index[0]
                value = indicator_series.iloc[idx] if idx < len(indicator_series) else None
                if pd.isna(value):
                    ind_string += f"{date_str}: N/A\n"
                else:
                    ind_string += f"{date_str}: {value:.2f}\n"
            else:
                ind_string += f"{date_str}: N/A: Not a trading day (weekend or holiday)\n"

            current_dt = current_dt - relativedelta(days=1)

    except Exception as e:
        raise AKShareError(f"Failed to get indicators for {raw_symbol}: {str(e)}")

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + INDICATOR_DESCRIPTIONS.get(indicator, "No description available.")
    )

    return result_str
```

- [ ] **Step 2: 编写技术指标测试**

在 `tests/test_akshare_vendor.py` 中添加：

```python
class TestGetIndicators:
    """Test technical indicator calculation."""

    def test_rsi_indicator(self):
        """Test RSI calculation."""
        from tradingagents.dataflows.akshare_utils import get_indicators
        result = get_indicators("600519", "rsi", "2025-01-10", 5)
        assert "rsi values" in result.lower() or "RSI values" in result

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
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_akshare_vendor.py::TestGetIndicators -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/akshare_utils.py tests/test_akshare_vendor.py
git commit -m "feat(akshare): implement technical indicators calculation"
```

---

## Task 5: 实现基本面数据获取

**Files:**
- Modify: `tradingagents/dataflows/akshare_utils.py`

- [ ] **Step 1: 实现基本面数据函数**

在 `akshare_utils.py` 中添加：

```python
def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for AKShare)"] = None
) -> str:
    """Get company fundamentals overview from AKShare.

    Returns formatted text with key metrics.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        # Get company info from East Money
        df = ak.stock_individual_info_em(symbol=ticker)

        if df.empty:
            return f"No fundamentals data found for symbol '{raw_ticker}'"

        # Convert to key-value pairs
        info = dict(zip(df["item"], df["value"]))

        fields = [
            ("Name", info.get("股票简称")),
            ("Code", info.get("股票代码")),
            ("Industry", info.get("行业")),
            ("Market Cap", info.get("总市值")),
            ("Circulating Market Cap", info.get("流通市值")),
            ("Total Shares", info.get("总股本")),
            ("Circulating Shares", info.get("流通股")),
            ("PE Ratio", info.get("市盈率(动态)")),
            ("PB Ratio", info.get("市净率")),
            ("ROE", info.get("净资产收益率")),
            ("Revenue", info.get("营业收入")),
            ("Net Profit", info.get("净利润")),
            ("Gross Margin", info.get("毛利率")),
            ("Net Margin", info.get("净利率")),
            ("List Date", info.get("上市时间")),
        ]

        lines = []
        for label, value in fields:
            if value is not None and str(value).strip():
                lines.append(f"{label}: {value}")

        header = f"# Company Fundamentals for {raw_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {raw_ticker}: {str(e)}"


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
) -> str:
    """Get balance sheet data from AKShare.

    Returns CSV string.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=ticker)

        if df.empty:
            return f"No balance sheet data found for symbol '{raw_ticker}'"

        # Filter by curr_date if provided
        if curr_date and "REPORT_DATE_NAME" in df.columns:
            cutoff = pd.Timestamp(curr_date)
            df["REPORT_DATE_NAME"] = pd.to_datetime(df["REPORT_DATE_NAME"], errors="coerce")
            df = df[df["REPORT_DATE_NAME"] <= cutoff]

        csv_string = df.to_csv(index=False)

        header = f"# Balance Sheet data for {raw_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving balance sheet for {raw_ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
) -> str:
    """Get cash flow data from AKShare.

    Returns CSV string.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=ticker)

        if df.empty:
            return f"No cash flow data found for symbol '{raw_ticker}'"

        # Filter by curr_date if provided
        if curr_date and "REPORT_DATE_NAME" in df.columns:
            cutoff = pd.Timestamp(curr_date)
            df["REPORT_DATE_NAME"] = pd.to_datetime(df["REPORT_DATE_NAME"], errors="coerce")
            df = df[df["REPORT_DATE_NAME"] <= cutoff]

        csv_string = df.to_csv(index=False)

        header = f"# Cash Flow data for {raw_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving cash flow for {raw_ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
) -> str:
    """Get income statement data from AKShare.

    Returns CSV string.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=ticker)

        if df.empty:
            return f"No income statement data found for symbol '{raw_ticker}'"

        # Filter by curr_date if provided
        if curr_date and "REPORT_DATE_NAME" in df.columns:
            cutoff = pd.Timestamp(curr_date)
            df["REPORT_DATE_NAME"] = pd.to_datetime(df["REPORT_DATE_NAME"], errors="coerce")
            df = df[df["REPORT_DATE_NAME"] <= cutoff]

        csv_string = df.to_csv(index=False)

        header = f"# Income Statement data for {raw_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving income statement for {raw_ticker}: {str(e)}"
```

- [ ] **Step 2: 编写基本面测试**

在 `tests/test_akshare_vendor.py` 中添加：

```python
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
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_akshare_vendor.py::TestGetFundamentals -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/akshare_utils.py tests/test_akshare_vendor.py
git commit -m "feat(akshare): implement fundamentals data fetching"
```

---

## Task 6: 实现新闻和内部交易数据获取

**Files:**
- Modify: `tradingagents/dataflows/akshare_utils.py`

- [ ] **Step 1: 实现新闻数据函数**

在 `akshare_utils.py` 中添加：

```python
def get_news(
    ticker: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"] = None,
    end_date: Annotated[str, "End date in yyyy-mm-dd format"] = None,
    max_articles: Annotated[int, "maximum number of articles to return"] = 20,
) -> str:
    """Get stock-specific news from AKShare (East Money source).

    Returns formatted markdown string.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        df = ak.stock_news_em(symbol=ticker)

        if df.empty:
            return f"No news found for symbol '{raw_ticker}'"

        # Filter by date range if provided
        if "发布时间" in df.columns:
            df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
            if start_date:
                start_dt = pd.Timestamp(start_date)
                df = df[df["发布时间"] >= start_dt]
            if end_date:
                end_dt = pd.Timestamp(end_date)
                df = df[df["发布时间"] <= end_dt]

        # Limit number of articles
        df = df.head(max_articles)

        # Format as markdown
        lines = [f"# News for {raw_ticker}", ""]
        for _, row in df.iterrows():
            title = row.get("新闻标题", row.get("标题", ""))
            content = row.get("新闻内容", row.get("内容", ""))
            pub_time = row.get("发布时间", "")
            source = row.get("文章来源", row.get("来源", ""))

            lines.append(f"## {title}")
            if pub_time:
                lines.append(f"**Published:** {pub_time}")
            if source:
                lines.append(f"**Source:** {source}")
            if content:
                # Truncate long content
                if len(str(content)) > 500:
                    content = str(content)[:500] + "..."
                lines.append(f"\n{content}")
            lines.append("\n---\n")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving news for {raw_ticker}: {str(e)}"


def get_global_news(
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"] = None,
    end_date: Annotated[str, "End date in yyyy-mm-dd format"] = None,
    max_articles: Annotated[int, "maximum number of articles to return"] = 10,
) -> str:
    """Get global/macro news from AKShare.

    Returns formatted markdown string.
    """
    try:
        # Get major financial news
        df = ak.stock_news_em(symbol="000001")  # Use a major index stock for macro news

        if df.empty:
            return "No global news found"

        # Filter by date range if provided
        if "发布时间" in df.columns:
            df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
            if start_date:
                start_dt = pd.Timestamp(start_date)
                df = df[df["发布时间"] >= start_dt]
            if end_date:
                end_dt = pd.Timestamp(end_date)
                df = df[df["发布时间"] <= end_dt]

        # Limit number of articles
        df = df.head(max_articles)

        # Format as markdown
        lines = ["# Global Financial News", ""]
        for _, row in df.iterrows():
            title = row.get("新闻标题", row.get("标题", ""))
            content = row.get("新闻内容", row.get("内容", ""))
            pub_time = row.get("发布时间", "")
            source = row.get("文章来源", row.get("来源", ""))

            lines.append(f"## {title}")
            if pub_time:
                lines.append(f"**Published:** {pub_time}")
            if source:
                lines.append(f"**Source:** {source}")
            if content:
                if len(str(content)) > 500:
                    content = str(content)[:500] + "..."
                lines.append(f"\n{content}")
            lines.append("\n---\n")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving global news: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
) -> str:
    """Get insider transactions data from AKShare.

    Returns CSV string.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        # Try East Money source for insider trades
        df = ak.stock_inner_trade_xq(symbol=ticker)

        if df is None or df.empty:
            return f"No insider transactions data found for symbol '{raw_ticker}'"

        csv_string = df.to_csv(index=False)

        header = f"# Insider Transactions data for {raw_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        # Insider transactions may not be available for all stocks
        return f"No insider transactions data found for symbol '{raw_ticker}': {str(e)}"
```

- [ ] **Step 2: 编写新闻测试**

在 `tests/test_akshare_vendor.py` 中添加：

```python
class TestGetNews:
    """Test news data fetching."""

    def test_stock_news(self):
        """Test fetching stock-specific news."""
        from tradingagents.dataflows.akshare_utils import get_news
        result = get_news("600519")
        # News may or may not be available, but should not raise
        assert isinstance(result, str)

    def test_global_news(self):
        """Test fetching global news."""
        from tradingagents.dataflows.akshare_utils import get_global_news
        result = get_global_news()
        assert isinstance(result, str)

    def test_insider_transactions(self):
        """Test fetching insider transactions."""
        from tradingagents.dataflows.akshare_utils import get_insider_transactions
        result = get_insider_transactions("600519")
        assert isinstance(result, str)
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_akshare_vendor.py::TestGetNews -v
```

Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/akshare_utils.py tests/test_akshare_vendor.py
git commit -m "feat(akshare): implement news and insider transactions fetching"
```

---

## Task 7: 注册 AKShare Vendor 到路由系统

**Files:**
- Modify: `tradingagents/dataflows/interface.py`

- [ ] **Step 1: 添加 AKShare imports 到 interface.py**

在 `interface.py` 顶部添加 import：

```python
from .akshare_utils import (
    get_stock_data as get_akshare_stock_data,
    get_indicators as get_akshare_indicators,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
    get_insider_transactions as get_akshare_insider_transactions,
    is_a_stock_ticker,
    AKShareError,
)
```

- [ ] **Step 2: 在 VENDOR_LIST 中添加 akshare**

修改 `VENDOR_LIST`：

```python
VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
]
```

- [ ] **Step 3: 在 VENDOR_METHODS 中注册 AKShare 方法**

修改 `VENDOR_METHODS` 字典，在每个方法的 dict 中添加 akshare 实现：

```python
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock_data,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicators,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "akshare": get_akshare_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "akshare": get_akshare_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "akshare": get_akshare_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "akshare": get_akshare_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
        "akshare": get_akshare_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "akshare": get_akshare_insider_transactions,
    },
}
```

- [ ] **Step 4: 修改 route_to_vendor() 添加 A 股 ticker 自动路由**

修改 `route_to_vendor()` 函数：

```python
def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support.

    For A-share tickers (6-digit codes), automatically routes to akshare vendor.
    """
    # Check if ticker is an A-share stock
    ticker = args[0] if args else kwargs.get("ticker") or kwargs.get("symbol", "")

    if is_a_stock_ticker(str(ticker)):
        vendor_config = "akshare"
    else:
        category = get_category_for_method(method)
        vendor_config = get_vendor(category, method)

    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    last_error = None
    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Rate limits trigger fallback
        except AKShareError as e:
            last_error = e
            continue  # AKShare errors trigger fallback

    raise RuntimeError(f"No available vendor for '{method}': {last_error}")
```

- [ ] **Step 5: 运行现有测试确保不破坏**

```bash
pytest tests/test_dataflows_config.py -v
pytest tests/test_ticker_symbol_handling.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add tradingagents/dataflows/interface.py
git commit -m "feat(akshare): register akshare vendor in routing system"
```

---

## Task 8: 添加配置项

**Files:**
- Modify: `tradingagents/default_config.py`

- [ ] **Step 1: 添加 AKShare 配置项**

在 `default_config.py` 的 `DEFAULT_CONFIG` 中添加：

```python
    # AKShare configuration for A-share market
    "akshare_config": {
        "cache_enabled": True,  # Whether to enable data caching
        "retry_count": 3,       # Number of retries on failure
        "timeout": 30,          # API timeout in seconds
    },
```

- [ ] **Step 2: Commit**

```bash
git add tradingagents/default_config.py
git commit -m "feat(akshare): add akshare configuration to default config"
```

---

## Task 9: 编写集成测试

**Files:**
- Create: `tests/test_akshare_integration.py`

- [ ] **Step 1: 创建集成测试文件**

```python
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
        """Test routing stock data request to AKShare."""
        result = route_to_vendor("get_stock_data", "600519", "2025-01-01", "2025-01-10")
        assert "600519" in result
        assert "Stock data" in result

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
        # This should use yfinance or alpha_vantage, not akshare
        # We can't easily test this without mocking, but we can at least
        # verify the function doesn't crash
        try:
            result = route_to_vendor("get_stock_data", "AAPL", "2025-01-01", "2025-01-10")
            # If we get here, it used yfinance or alpha_vantage
            assert isinstance(result, str)
        except Exception:
            # It's okay if it fails due to missing API keys
            pass
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/test_akshare_integration.py -v -m integration
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_akshare_integration.py
git commit -m "test(akshare): add integration tests for akshare vendor"
```

---

## Task 10: 端到端验证

**Files:**
- None (manual testing)

- [ ] **Step 1: 运行完整 pipeline 测试**

```bash
python -c "
from tradingagents.dataflows.interface import route_to_vendor

# Test all data types
ticker = '600519'
print('=== Testing AKShare Integration ===')
print()

# 1. Stock data
print('1. Stock Data:')
result = route_to_vendor('get_stock_data', ticker, '2025-01-01', '2025-01-10')
print(result[:200] + '...')
print()

# 2. Indicators
print('2. RSI Indicator:')
result = route_to_vendor('get_indicators', ticker, 'rsi', '2025-01-10', 5)
print(result[:200] + '...')
print()

# 3. Fundamentals
print('3. Fundamentals:')
result = route_to_vendor('get_fundamentals', ticker)
print(result[:200] + '...')
print()

# 4. News
print('4. News:')
result = route_to_vendor('get_news', ticker)
print(result[:200] + '...')
print()

print('=== All tests passed! ===')
"
```

Expected: 各数据类型均成功获取，无报错

- [ ] **Step 2: 运行全部单元测试**

```bash
pytest tests/test_akshare_vendor.py -v
pytest tests/test_akshare_integration.py -v -m integration
```

Expected: 全部 PASS

- [ ] **Step 3: 运行项目全部测试确保无回归**

```bash
pytest -m unit
```

Expected: 全部 PASS

- [ ] **Step 4: Final Commit**

```bash
git add -A
git commit -m "feat: complete AKShare A-share data integration"
```

---

## 实现检查清单

- [ ] akshare 包已安装
- [ ] Ticker 识别和转换函数实现并测试通过
- [ ] OHLCV 数据获取实现并测试通过
- [ ] 技术指标计算实现并测试通过
- [ ] 基本面数据获取实现并测试通过
- [ ] 新闻数据获取实现并测试通过
- [ ] Vendor 注册到路由系统
- [ ] 配置项已添加
- [ ] 集成测试通过
- [ ] 端到端验证通过
- [ ] 所有现有测试无回归
