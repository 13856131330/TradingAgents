# AKShare A股数据集成设计文档

## 概述

集成 AKShare 作为 A 股数据专用 vendor，为 TradingAgents 框架提供最新的 A 股行情、基本面、技术指标和新闻数据。用户输入纯 6 位数字 ticker（如 `600519`），系统自动识别并路由到 AKShare 获取数据。

## 目标

- 支持 A 股全数据类型：OHLCV、基本面、技术指标、新闻
- 自动识别 A 股 ticker 格式，无需用户手动配置
- 保持与现有 vendor routing 架构一致
- 支持缓存和错误处理

## 架构设计

### 1. 新增文件

**`tradingagents/dataflows/akshare_utils.py`**

实现以下 9 个方法：

| 方法名 | AKShare API | 返回格式 | 说明 |
|--------|------------|---------|------|
| `get_stock_data` | `ak.stock_zh_a_hist()` | CSV 字符串 | 日线 OHLCV 数据 |
| `get_indicators` | 基于 OHLCV 计算 | 与 yfinance 一致 | SMA, EMA, MACD, RSI, 布林带等 |
| `get_fundamentals` | `ak.stock_individual_info_em()` | 格式化文本 | 公司基本信息（PE, EPS, 市值等） |
| `get_balance_sheet` | `ak.stock_balance_sheet_by_report_em()` | CSV 字符串 | 资产负债表 |
| `get_cashflow` | `ak.stock_cash_flow_sheet_by_report_em()` | CSV 字符串 | 现金流量表 |
| `get_income_statement` | `ak.stock_profit_sheet_by_report_em()` | CSV 字符串 | 利润表 |
| `get_news` | `ak.stock_news_em()` | Markdown | 个股新闻 |
| `get_global_news` | `ak.stock_news_em()` + 宏观 | Markdown | 全局/宏观新闻 |
| `get_insider_transactions` | `ak.stock_inner_trade_xq()` | CSV 字符串 | 内部交易 |

### 2. 修改文件

**`tradingagents/dataflows/interface.py`**

- 在 `VENDOR_LIST` 中添加 `"akshare"`
- 在 `VENDOR_METHODS` 中注册所有 9 个方法的 AKShare 实现
- 在 `route_to_vendor()` 中添加 A 股 ticker 检测逻辑
- 新增 `is_a_stock_ticker()` 函数

**`tradingagents/default_config.py`**

- 添加 AKShare 相关配置项

### 3. Ticker 识别与转换

**识别规则**：
```python
def is_a_stock_ticker(ticker: str) -> bool:
    """判断是否为 A 股 ticker"""
    # 纯 6 位数字
    if re.match(r'^\d{6}$', ticker):
        return True
    # 带 .SH/.SZ 后缀
    if re.match(r'^\d{6}\.(SH|SZ)$', ticker.upper()):
        return True
    # 带 sh/sz 前缀
    if re.match(r'^(sh|sz)\d{6}$', ticker.lower()):
        return True
    return False
```

**转换规则**：
```python
def normalize_a_stock_ticker(ticker: str) -> str:
    """转换为 AKShare 所需的纯数字格式"""
    ticker = ticker.strip()
    # 去除 .SH/.SZ 后缀
    if '.' in ticker:
        ticker = ticker.split('.')[0]
    # 去除 sh/sz 前缀
    if ticker.lower().startswith(('sh', 'sz')):
        ticker = ticker[2:]
    return ticker
```

### 4. 路由逻辑

在 `route_to_vendor()` 中增加 A 股检测：

```python
def route_to_vendor(method: str, ticker: str, **kwargs):
    # 新增：A 股 ticker 自动路由到 AKShare
    if is_a_stock_ticker(ticker):
        vendor = "akshare"
    else:
        # 原有逻辑：从配置获取 vendor
        category = get_category_for_method(method)
        vendor = get_vendor(category, method)
    
    # 后续 fallback 逻辑不变
    ...
```

### 5. 技术指标计算

使用 pandas 手动计算，不依赖 stockstats 库：

```python
def calculate_indicators(df: pd.DataFrame) -> dict:
    """计算技术指标"""
    indicators = {}
    
    # SMA
    indicators['close_50_sma'] = df['close'].rolling(50).mean()
    indicators['close_200_sma'] = df['close'].rolling(200).mean()
    
    # EMA
    indicators['close_10_ema'] = df['close'].ewm(span=10).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    indicators['macd'] = ema12 - ema26
    indicators['macds'] = indicators['macd'].ewm(span=9).mean()
    indicators['macdh'] = indicators['macd'] - indicators['macds']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    indicators['rsi'] = 100 - (100 / (1 + rs))
    
    # 布林带
    indicators['close_20_sma'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    indicators['boll_ub'] = indicators['close_20_sma'] + 2 * std
    indicators['boll_lb'] = indicators['close_20_sma'] - 2 * std
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    indicators['atr'] = tr.rolling(14).mean()
    
    return indicators
```

### 6. 缓存策略

**共享缓存目录**：`~/.tradingagents/cache/`

**缓存 key 格式**：`{vendor}_{ticker}_{start_date}_{end_date}.csv`

示例：
- yfinance: `yfinance_600519_2024-01-01_2024-12-31.csv`
- akshare: `akshare_600519_2024-01-01_2024-12-31.csv`

复用 `stockstats_utils.py` 中的 `load_ohlcv()` 函数，通过 vendor 参数区分。

### 7. 错误处理

**自定义异常**：
```python
class AKShareError(Exception):
    """AKShare API 调用异常"""
    pass
```

**重试机制**：
- 复用 `yf_retry()` 的指数退避逻辑
- 最多重试 3 次
- 网络超时、API 限频时触发重试

**Fallback 链**：
- AKShare 失败时，抛出 `AKShareError`
- `route_to_vendor()` 捕获后尝试下一个 vendor
- 配置示例：`"akshare,yfinance"` 表示 AKShare 优先，失败回退 yfinance

## 配置项

在 `default_config.py` 中添加：

```python
# AKShare 配置
"akshare_config": {
    "cache_enabled": True,  # 是否启用缓存
    "retry_count": 3,       # 重试次数
    "timeout": 30,          # API 超时时间（秒）
}
```

## 测试计划

1. **单元测试**：
   - `is_a_stock_ticker()` 各种格式识别
   - `normalize_a_stock_ticker()` 转换正确性
   - 技术指标计算准确性

2. **集成测试**：
   - AKShare API 调用成功
   - 数据格式与现有系统兼容
   - 缓存读写正常

3. **端到端测试**：
   - 输入 `600519`，完整 pipeline 执行成功
   - 生成的报告包含最新 A 股数据

## 依赖

- `akshare` Python 包
- 现有依赖：`pandas`, `numpy`

## 实现顺序

1. 新建 `akshare_utils.py`，实现基础 OHLCV 获取
2. 实现技术指标计算
3. 实现基本面数据获取
4. 实现新闻数据获取
5. 修改 `interface.py`，注册 vendor 和路由逻辑
6. 修改 `default_config.py`，添加配置项
7. 编写测试
8. 集成测试和调试
