"""AKShare data provider for A-share market."""

import re
from datetime import datetime
from typing import Annotated, Optional

import pandas as pd
import akshare as ak
from dateutil.relativedelta import relativedelta


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
            raise AKShareError(f"No data found for symbol '{raw_symbol}'")

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


def _normalize_for_financial_api(ticker: str) -> str:
    """Convert A-share ticker to SH/SZ prefix format for financial report APIs.

    Examples:
    - 600519 -> SH600519
    - 000001 -> SZ000001
    - 300750 -> SZ300750
    - 600519.SH -> SH600519
    - sh600519 -> SH600519
    """
    ticker = ticker.strip()
    # Remove .SH/.SZ suffix
    if '.' in ticker:
        suffix = ticker.split('.')[1].upper()
        code = ticker.split('.')[0]
        return suffix + code
    # Remove sh/sz prefix and re-add uppercase
    if ticker.lower().startswith(('sh', 'sz')):
        return ticker[:2].upper() + ticker[2:]
    # Pure 6-digit: infer exchange from code
    if re.match(r'^\d{6}$', ticker):
        if ticker.startswith(('6', '9')):
            return 'SH' + ticker
        else:
            return 'SZ' + ticker
    return ticker


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for AKShare)"] = None
) -> str:
    """Get company fundamentals overview from AKShare.

    Returns formatted text with key metrics.
    Uses stock_profile_cninfo (cninfo.com.cn) as primary source,
    with stock_individual_info_em (East Money) as fallback.
    """
    raw_ticker = ticker
    if is_a_stock_ticker(ticker):
        ticker = normalize_a_stock_ticker(ticker)

    try:
        # Try cninfo profile first (more reliable)
        df = ak.stock_profile_cninfo(symbol=ticker)

        if df is not None and not df.empty:
            info = df.iloc[0].to_dict()

            fields = [
                ("Name", info.get("公司名称")),
                ("English Name", info.get("英文名称")),
                ("A-Share Code", info.get("A股代码")),
                ("A-Share Short Name", info.get("A股简称")),
                ("Market", info.get("所属市场")),
                ("Industry", info.get("所属行业")),
                ("Legal Representative", info.get("法人代表")),
                ("Registered Capital", info.get("注册资金")),
                ("List Date", info.get("上市日期")),
                ("Founded Date", info.get("成立日期")),
                ("Website", info.get("官方网站")),
                ("Main Business", info.get("主营业务")),
            ]

            lines = []
            for label, value in fields:
                if value is not None and str(value).strip() and str(value) != "None":
                    # Truncate very long text fields
                    val_str = str(value).strip()
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    lines.append(f"{label}: {val_str}")

            header = f"# Company Fundamentals for {raw_ticker}\n"
            header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            return header + "\n".join(lines)

    except Exception:
        pass  # Fall through to East Money API

    try:
        # Fallback: East Money individual info
        df = ak.stock_individual_info_em(symbol=ticker)

        if df is None or df.empty:
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
        ticker = _normalize_for_financial_api(ticker)

    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=ticker)

        if df is None or df.empty:
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
        ticker = _normalize_for_financial_api(ticker)

    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=ticker)

        if df is None or df.empty:
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
        ticker = _normalize_for_financial_api(ticker)

    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=ticker)

        if df is None or df.empty:
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
