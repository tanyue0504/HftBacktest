# HftBacktest

**HftBacktest** 是一个基于 Python 的高性能、事件驱动的高频交易回测框架。

它专为模拟真实交易环境而设计，采用了 **Server-Client 双端架构**，通过模拟网络延迟总线（DelayBus）连接策略端与交易所端，能够精确回测高频策略在延迟环境下的表现。核心组件使用 **Cython** 编写以确保极高的事件处理吞吐量。

## ✨ 核心特性

* **双端架构 (Dual-Engine)**: 分离交易所（Server）与策略（Client）的事件循环，真实模拟 C/S 架构。
* **延迟模拟 (Network Latency)**: 内置 `DelayBus` 组件，支持自定义网络延迟（RTT），模拟行情推送与订单回报的异步延迟。
* **高性能核心**: 核心事件对象 (`Event`) 和订单对象 (`Order`) 采用 Cython 实现，大幅降低内存占用并提升处理速度。
* **全功能撮合**: 
    * **OKX/Binance Matcher**: 支持 Level-2 25档盘口数据的精确撮合，包含 Maker/Taker 费率及排队位置估算 (Rank-based matching)。
    * **Bar Matcher**: 支持分钟/小时级 K 线数据的低频回测。
* **混合数据源**: 支持 `Parquet` 和 `CSV` 格式，支持多数据源（如 Trades + BookTicker + FundingRate）按时间戳归并回放。
* **精确结算**: 内置账户会计核算系统，支持保证金、手续费、资金费率及交割结算逻辑。

## 🛠️ 安装指南

### 前置条件
* Python 3.8+
* C++ 编译器 (用于编译 Cython 扩展)

### 安装步骤

1.  **克隆仓库**
    ```bash
    git clone [https://github.com/your-repo/hft_backtest.git](https://github.com/your-repo/hft_backtest.git)
    cd hft_backtest
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

3.  **编译 Cython 扩展**
    这是必须的步骤，用于生成核心的 C 扩展模块。
    ```bash
    python setup.py build_ext --inplace
    ```

## 🚀 快速开始

以下是一个简单的回测流程示例：

```python
from hft_backtest import BacktestEngine, Order, Strategy, Data
from hft_backtest.binance import BinanceAccount, BinanceMatcher, BinanceRecorder
# 假设你已经定义了 BinanceData 类用于读取 parquet

class MyStrategy(Strategy):
    def on_data(self, data: Data):
        # 简单的策略逻辑
        if data.name == 'bookTicker':
             # 打印行情或下单
             pass

# 1. 准备数据
bookticker_ds = BinanceData('bookTicker', "./data/bookTicker.parquet", timecol="transaction_time")
trades_ds = BinanceData('trades', "./data/trades.parquet", timecol="time")

# 2. 初始化回测引擎，设置 10ms 延迟
backtest_engine = BacktestEngine(datasets=[bookticker_ds, trades_ds], delay=10)

# 3. 配置服务端组件 (交易所侧)
backtest_engine.add_component(BinanceMatcher(), is_server=True)
backtest_engine.add_component(BinanceAccount(), is_server=True)
backtest_engine.add_component(BinanceRecorder("./record", snapshot_interval=60000), is_server=True)

# 4. 配置客户端组件 (策略侧)
local_account = BinanceAccount() # 本地影子账户
strategy = MyStrategy(local_account)
backtest_engine.add_component(local_account, is_server=False)
backtest_engine.add_component(strategy, is_server=False)

# 5. 运行回测
backtest_engine.run()