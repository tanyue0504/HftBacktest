# HftBacktest

**HftBacktest** 是一个专为高频交易（HFT）设计的高性能、事件驱动回测框架。

它采用 **Python + Cython/C++** 的混合架构，在保持策略开发灵活性的同时，利用底层编译代码极大地提升了事件循环、订单撮合及数据回放的性能。框架核心致力于解决高频回测中的痛点：**真实的网络延迟模拟**、**微观结构下的订单排队**以及**高吞吐量的历史数据回放**。

---

## ✨ 核心特性 (Key Features)

* **⚡ 极致性能 (High Performance)**:
    * 核心组件（事件引擎、订单管理、数据读取）均使用 **Cython** 和 **C++** 编写，大幅降低 Python GIL 带来的开销。
    * 支持 **Parquet** 格式数据的高效流式读取，能够轻松处理 TB 级别的 Tick/Depth 数据。
    * 核心事件对象（Event）经过内存布局优化，减少 GC 压力。

* **🕸️ 真实的延迟模拟 (Realistic Latency)**:
    * 独创的 **双引擎架构 (Dual-Engine Architecture)**：将“本地策略端”与“交易所服务端”逻辑严格物理隔离。
    * **DelayBus (延迟总线)**：在两端之间建立带有延迟的传输通道。支持模拟 **网络传输延迟 (One-way Latency)**，精确还原行情推送滞后（Server->Client）和订单回报滞后（Server->Client）以及下单请求滞后（Client->Server）的真实异步场景。

* **📊 微观结构仿真 (Microstructure Simulation)**:
    * 内置高精度的 **本地撮合引擎 (Matching Engine)**，支持通过订单流（Trades）和盘口数据（BookTicker/Depth）估算限价单在 OrderBook 中的 **排队位置 (Queue Position)**。
    * 提供 **Binance** 和 **OKX** 等主流交易所的特定规则适配（如不同的费率模型、订单类型）。

* **🧩 组件化设计 (Component-Based)**:
    * 系统高度解耦，策略、账户、撮合器、风控模块均作为独立组件（Component）接入事件总线。
    * 支持自定义数据源（Dataset）和因子计算模块（Factor）。

---

## 🏗️ 系统架构 (Architecture)

HftBacktest 模拟了真实的物理交易链路。整个回测环境由两个独立的事件循环（Event Loop）组成，中间通过延迟总线连接。

```mermaid
graph TD
    subgraph "Server Engine (交易所端)"
        Matcher[撮合引擎<br/>Matching Engine]
        ServerAcc[交易所账户<br/>Exchange Account]
        Settlement[结算/费率<br/>Settlement]
    end

    subgraph "Client Engine (策略端)"
        Strategy[用户策略<br/>User Strategy]
        ClientAcc[本地影子账户<br/>Shadow Account]
        Risk[风控模块<br/>Risk Manager]
    end

    %% 数据流向
    Data[历史数据流<br/>Merged Dataset] -->|原始行情 (Book/Trade)| ServerEngine
    
    %% 内部交互 (无延迟)
    ServerEngine <==> Matcher
    ServerEngine <==> ServerAcc
    
    ClientEngine <==> Strategy
    ClientEngine <==> ClientAcc

    %% 跨网络交互 (带延迟)
    ServerEngine -.->|行情推送 / 订单回报 (Latency)| BusS2C[DelayBus: Server -> Client]
    BusS2C -.-> ClientEngine
    
    ClientEngine -.->|下单请求 / 撤单请求 (Latency)| BusC2S[DelayBus: Client -> Server]
    BusC2S -.-> ServerEngine
```

---

## 📚 文档导航（建议阅读顺序）

这份 README 以“能用 → 能改 → 能研究”的顺序组织内容。

### 第一阶段：让读者能用

1) [**快速开始**](#quick-start)：跑通一个 OKX 端到端回测（数据 → 双引擎 → 双 DelayBus → 撮合/账户/策略）。
2) [**核心概念**](#core-concepts)：理解 `Event`/`EventEngine`/`DelayBus`/`Order`/`Component` 的语义与边界。
3) [**OKX 数据 schema**](#okx-schema)：ArrayReader 期望列、字段单位与约定。
4) [**数据准备**](#data-prep)：Event 模式 vs Batch+ArrayReader 模式。

### 第二阶段：让读者能改

5) [**扩展指南**](#extensions)：自定义延迟模型、Component、事件与 Reader。
6) **新交易所适配清单**：要实现哪些 `Event/Matcher/Account/Reader`，如何接到双引擎链路。

### 第三阶段：让读者能研究

7) [**研究闭环**](#research)：因子采样、标签、评估报告。
8) [**性能与故障排查**](#troubleshooting)：构建、版本、热点路径、常见坑。

### 建议从这些文件开始读（从“概念”到“实现”）

- 事件与时间：
    - `Event`：[hft_backtest/event.pyx](hft_backtest/event.pyx)
    - `Timer`：[hft_backtest/timer.pyx](hft_backtest/timer.pyx)
    - 派发器：`EventEngine`：[hft_backtest/event_engine.pyx](hft_backtest/event_engine.pyx)
- 回测主循环：`BacktestEngine`：[hft_backtest/backtest.pyx](hft_backtest/backtest.pyx)
- “网线”与延迟：`DelayBus/LatencyModel`：[hft_backtest/delaybus.pyx](hft_backtest/delaybus.pyx)
- 订单协议：`Order`：[hft_backtest/order.pyx](hft_backtest/order.pyx)
- Component 与工具：
    - 基类：`Strategy`：[hft_backtest/strategy.py](hft_backtest/strategy.py)
    - 打印/追踪：[hft_backtest/helper.py](hft_backtest/helper.py)
    - 记录器：[hft_backtest/recorder.py](hft_backtest/recorder.py)
- OKX 适配：
    - 事件 schema：[hft_backtest/okx/event.pyx](hft_backtest/okx/event.pyx)
    - 高性能 Reader：[hft_backtest/okx/reader.pyx](hft_backtest/okx/reader.pyx)
    - 撮合器：[hft_backtest/okx/matcher.pyx](hft_backtest/okx/matcher.pyx)
    - 账户结算：[hft_backtest/okx/account.pyx](hft_backtest/okx/account.pyx)
    - 因子评估（可选）：[hft_backtest/okx/factor_evaluator.pyx](hft_backtest/okx/factor_evaluator.pyx)

---

## 🚀 安装指南 (Installation)

由于本项目包含大量 Cython/C++ 扩展代码，建议使用本地编译安装。

### 1. 环境准备 (Prerequisites)

- **OS**: Linux (推荐) / Windows / MacOS
- **Python**: 建议 **3.8 - 3.10**。
- **重要**：目前不支持 Python 3.11+（Cython 扩展兼容性问题）。
- **Compiler**:
    - Linux/MacOS: GCC 或 Clang
    - Windows: Microsoft Visual C++ 14.0+ (Build Tools)

### 2. 安装依赖与开发安装

```bash
pip install -U pip setuptools wheel
pip install -e .
```

### 3. 编译扩展 (Build Extensions)

```bash
python setup.py build_ext --inplace
```

### 4. (可选) 调试模式编译

```bash
# Linux/Mac
HFT_DEBUG=1 python setup.py build_ext --inplace

# Windows (PowerShell)
$env:HFT_DEBUG="1"; python setup.py build_ext --inplace
```

---

<a id="core-concepts"></a>
## 🧩 核心概念（Event / Engine / Bus / Order / Component）

### 1) Event：框架里“唯一的消息载体”

所有数据、订单、定时器、因子信号最终都是 `Event`（或其子类）。核心字段：

- `timestamp`：事件发生的逻辑时间（排序与时间推进的唯一依据）
- `source`：产生该事件的引擎 id（ServerEngine 或 ClientEngine）
- `producer`：产生该事件的 listener id（用于 `ignore_self` 去自反馈）

`derive()`：用于在延迟传输/跨组件处理时做“快照复制”。`DelayBus` 会对每个要传输的事件做 `derive()`，避免发送方后续修改对象污染延迟队列。

### 2) EventEngine：高性能派发器（单线程事件循环）

`EventEngine` 负责两件事：

1. 维护引擎当前时间 `engine.timestamp`（`put(event)` 时自动推进）
2. 按监听器顺序派发事件（见 [hft_backtest/event_engine.pyx](hft_backtest/event_engine.pyx)）：
     - Senior Global → Specific Type Listeners → Junior Global

两个常用注册接口：

- `engine.register(EventType, callback, ignore_self=True)`：只监听某类事件
- `engine.global_register(callback, ignore_self=False, is_senior=False)`：监听所有事件

`ignore_self` 的语义是：如果当前事件的 `producer` 是自己，就跳过回调，避免“组件 A 收到事件 → 再 put → 又被自己收到”的自触发回路。

### 3) Component：可插拔功能单元

Component 是“扩展机制”的核心：任何想挂进系统的功能都写成 Component。

- 生命周期：`start(engine)` / `stop()`
- 推荐做法：
    - 在 `start()` 里注册回调（`engine.register`/`global_register`）
    - 在回调里读事件、更新内部状态、必要时 `engine.put(new_event)`

策略、撮合器、账户、DelayBus、Recorder、因子采样器本质上都是 Component。

### 4) DelayBus：两套引擎之间的“带延迟网线”

- 只搬运来自某一侧引擎（source id 匹配）的事件
- 对 `event` 做 `derive()` 得到副本 `snapshot`
- 使用 `LatencyModel.get_delay(event)` 计算触发时间 `event.timestamp + delay`
- 到点后把 `snapshot` 推送到目标引擎

### 5) Order：订单协议与状态机

`Order` 是一个高性能 Cython 事件类型（见 [hft_backtest/order.pyx](hft_backtest/order.pyx)）：

- **方向**：由 `quantity` 正负决定（`>0` 买，`<0` 卖）
- **价格/数量整数化**：内部用 `SCALER` 缓存 `price_int/quantity_int`，减少浮点误差与计算开销
- **常用创建方法**：
    - `Order.create_limit(symbol, quantity, price, post_only=False)`
    - `Order.create_market(symbol, quantity)`
    - `Order.create_tracking(symbol, quantity, post_only=True)`（跟踪最优价）
    - `Order.create_cancel(order)`

订单生命周期（典型）：

`CREATED → SUBMITTED → RECEIVED → (FILLED | CANCELED | REJECTED)`

策略发单时会把订单从 `CREATED` 推到 `SUBMITTED`（见 [hft_backtest/strategy.py](hft_backtest/strategy.py)）。

---

## 🧱 现有组件一览（怎么用 / 放在哪边）

下面列出仓库里“已经内置”的常用 Component，以及它们通常挂在哪个引擎侧：

- **基础设施**
    - `DelayBus`：两侧都要挂（S2C 与 C2S），负责跨引擎搬运事件。
    - `EventPrinter`：[hft_backtest/helper.py](hft_backtest/helper.py)（调试用，通常挂在你想观察的那侧）。
    - `OrderTracer`：[hft_backtest/helper.py](hft_backtest/helper.py)（调试指定订单 id 的全生命周期）。

- **交易闭环（OKX）**
    - `OKXMatcher`：[hft_backtest/okx/matcher.pyx](hft_backtest/okx/matcher.pyx)（Server 侧）。
    - `OKXAccount`：[hft_backtest/okx/account.pyx](hft_backtest/okx/account.pyx)（Server 侧结算；Client 侧可作为影子账户）。

- **记录与观测**
    - `TradeRecorder` / `AccountRecorder` / `OrderRecorder`：[hft_backtest/recorder.py](hft_backtest/recorder.py)
        - 通过监听 `Order` 或 `Timer` 事件落盘（通常挂在 Client 侧更贴近策略视角；也可两侧都挂）。

- **研究闭环（因子/标签/评估）**
    - `FactorSignal`：[hft_backtest/factor.pyx](hft_backtest/factor.pyx)（事件协议，本身不是 Component）。
    - `FactorSampler`：[hft_backtest/factor_sampler.pyx](hft_backtest/factor_sampler.pyx)（Timer 驱动采样，通常挂 Client）。
    - `OKXLabelSampler`：[hft_backtest/okx/label_sampler.py](hft_backtest/okx/label_sampler.py)（Timer 驱动标签，通常挂 Client）。
    - `FactorMarketSampler`：[hft_backtest/okx/factor_market_sampler.py](hft_backtest/okx/factor_market_sampler.py)（基于固定 interval 对齐市场收益）。
    - `FactorEvaluator`：[hft_backtest/okx/factor_evaluator.pyi](hft_backtest/okx/factor_evaluator.pyi)（统计与报告）。

---

<a id="okx-schema"></a>
## 🧾 OKX 数据 schema（ArrayReader 期望列）

如果你希望使用 [hft_backtest/okx/reader.pyx](hft_backtest/okx/reader.pyx) 的高性能 ArrayReader，需要保证输入 DataFrame（来自 Parquet/CSV 读出来的列）满足以下字段约定。

### OKXTradesArrayReader

期望列名：

- `created_time`：int64，事件时间戳（示例中用 us）
- `trade_id`：int64
- `price`：float64
- `size`：float64
- `instrument_name`：str（例如 `BTC-USDT`）
- `side`：str（例如 `buy`/`sell`）

### OKXBooktickerArrayReader

必需列：

- `timestamp`：int64
- `symbol`：str

可选列：

- `local_timestamp`：int64（没有则 Reader 会补 0）

深度列（建议齐全；缺失会被补 0）：

- `ask_price_1..25`, `ask_amount_1..25`
- `bid_price_1..25`, `bid_amount_1..25`

---

<a id="extensions"></a>
## 🧰 扩展指南（能改：自定义延迟 / 自定义组件 / 新交易所）

### 1) 自定义延迟模型（LatencyModel）

实现 `LatencyModel.get_delay(event)`，返回“单向延迟”（单位与你的 `timestamp` 单位一致）：

```python
from hft_backtest.delaybus import LatencyModel

class MyLatency(LatencyModel):
        def __init__(self, base_delay: int = 5000):
                self.base_delay = int(base_delay)

        def get_delay(self, event):
                # 示例：对 Order 增加额外 2ms
                from hft_backtest.order import Order
                if isinstance(event, Order):
                        return self.base_delay + 2000
                return self.base_delay
```

### 2) 如何写一个 Component（通用扩展方式）

你可以用 Component 把任何功能挂进事件流：风控、统计、订单节流、日志、指标、采样器……

最小模板：

```python
from hft_backtest.event_engine import Component, EventEngine

class MyComponent(Component):
        def start(self, engine: EventEngine):
                self.engine = engine
                # engine.register(SomeEvent, self.on_event)

        def stop(self):
                pass
```

### 3) 如何根据数据定义新的事件（Event）

两种路线：

- **Python 事件类**（简单，但性能一般；适合原型验证）
- **Cython 事件类**（推荐；用于高频/大吞吐）

如果你要做 Cython 事件：

1. 新建 `hft_backtest/<exchange>/event.pyx`（以及必要的 `.pxd`/`.pyi`）定义 `cdef class` 与 `cdef public` 字段
2. 为该事件实现 `derive()`（建议手写字段拷贝，避免 `copy.copy` 的额外开销）
3. 在 [setup.py](setup.py) 的 `extensions` 里加入该模块
4. `python setup.py build_ext --inplace`

可以参考 OKX 的实现：[hft_backtest/okx/event.pyx](hft_backtest/okx/event.pyx)。

### 4) 如何写高性能读取器（DataReader / ArrayReader）

当你需要处理 TB 级别数据或极高吞吐时，建议走：

`ParquetDataset(mode='batch') → (DataFrame batch) → *ArrayReader(DataReader) → Event 流`。

写 Reader 的关键 checklist（参考 [hft_backtest/okx/reader.pyx](hft_backtest/okx/reader.pyx)）：

- 从 batch DataFrame 里把列一次性转成 numpy array（`astype(np.int64/np.float64)`）
- **保活** DataFrame / numpy array（否则底层指针会悬空）
- `fetch_next()` 里用 `__new__` 创建事件对象并直接字段赋值（避免 Python 层构造开销）
- 批次读完时再加载下一批，避免逐行 Python 循环

### 5) 新交易所适配清单（最重要）

要把一个新交易所接入到“双引擎 + 双 DelayBus”的框架里，通常需要：

1. **事件定义**：至少包含盘口/成交（可能还有资金费/交割/指数价等）。
2. **撮合器**：继承 `MatchEngine`，在 `start()` 注册：
     - `engine.register(Order, self.on_order)`
     - `engine.register(MarketEvent, self.on_market)`
     并在撮合状态变化时 `engine.put(order_update)`。
3. **账户**：继承 `Account`，监听 `Order` 回报与交易所事件，更新现金/仓位/费用。
4. **读取器（可选但强烈建议）**：为该交易所的 schema 写 `*ArrayReader`。
5. **文档与 schema**：明确输入数据列名、时间单位、symbol 规范。

---

<a id="research"></a>
## 🔬 研究闭环（因子采样 / 标签 / 评估）

这一套组件让你能把“策略侧的因子信号”与“市场后验收益/标签”对齐，形成研究数据集。

### 1) FactorSignal：因子事件协议

`FactorSignal(symbol, value, name)` 是一个事件（见 [hft_backtest/factor.pyx](hft_backtest/factor.pyx)）。策略或因子组件可以把它 `put` 到引擎里。

### 2) Timer 对齐：FactorSampler / OKXLabelSampler

- `BacktestEngine` 会按 `timer_interval` 往 ClientEngine 注入 `Timer(timestamp)`。
- `FactorSampler` 监听 `Timer` 与 `FactorSignal`，在每个 timer tick 输出一个“截面快照”。
- `OKXLabelSampler` 监听 `Timer` 与 `OKXBookticker`，生成对应时间的收益标签 `y`。

### 3) Market 对齐：FactorMarketSampler

如果你更喜欢固定 interval 的“边界价差”定义（更接近 bar-return），可以用 `FactorMarketSampler`（见 [hft_backtest/okx/factor_market_sampler.py](hft_backtest/okx/factor_market_sampler.py)）。

### 4) 评估：FactorEvaluator

`FactorEvaluator` 会把因子与 forward return 的关系做统计汇总，并输出报告（见 [hft_backtest/okx/factor_evaluator.pyi](hft_backtest/okx/factor_evaluator.pyi)）。

---

<a id="troubleshooting"></a>
## 🧯 性能与故障排查（必读）

### 1) Python 版本

当前版本请使用 Python 3.10/3.9/3.8。Python 3.11+ 可能导致扩展编译失败或运行时异常。

### 2) 常见导入问题

- `ImportError: ... .so not found`：通常是忘了 `python setup.py build_ext --inplace` 或编译失败。
- `AttributeError`/奇怪崩溃：优先检查 Python 版本与编译产物是否与当前解释器一致。

### 3) 性能建议（优先级从高到低）

- 读数据优先走 `batch + ArrayReader` 路线
- 避免在策略回调里做重 pandas 操作（把 heavy compute 做成离线或用 numpy）
- 事件里尽量只放必要字段；不要频繁挂动态属性
- Recorder 写盘用 buffer（项目内 Recorder 已做 buffer）

---

<a id="quick-start"></a>
## ⚡ 快速开始 (Quick Start)

### 1. 运行最小示例

为了让您快速上手，我们提供了一个最小化的 Demo。请在项目根目录下创建一个名为 `demo.py` 的文件。

**注意**：此 Demo 会在本地生成两份 Parquet（`./data/trades.parquet` 与 `./data/bookTicker.parquet`），无需外部数据；如果你要接入真实数据，请看下方“数据准备”。

```python
# demo.py
import time
import os
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from hft_backtest import (
    BacktestEngine, 
    MergedDataset, 
    ParquetDataset, 
    Strategy, 
    Order,
)
from hft_backtest.delaybus import DelayBus, FixedDelayModel
# 使用 OKX 组件（建议直接从子模块导入，避免 __init__ 暴露不全）
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.okx.reader import OKXBooktickerArrayReader, OKXTradesArrayReader
from hft_backtest.okx.event import OKXBookticker

# ==============================================================================
# 0. 数据生成工具 (仅用于 Demo，无需外部文件)
# ==============================================================================
def generate_dummy_data():
    """生成测试用的 parquet 数据文件"""
    if not os.path.exists("./data"):
        os.makedirs("./data")
    
    # 1. 生成 OKX Trades 数据 (100条)
    # OKXTradesArrayReader 期望字段：created_time/trade_id/price/size/instrument_name/side
    trades_df = pd.DataFrame({
        'created_time': range(1000, 101000, 1000), # 时间单位示例：us
        'trade_id': range(1, 101),
        'price': [50000.0 + i * 0.1 for i in range(100)],
        'size': 0.1,
        'instrument_name': 'BTC-USDT',
        'side': 'buy',
    })
    # 转换为 Parquet (禁用索引)
    pq.write_table(pa.Table.from_pandas(trades_df, preserve_index=False), "./data/trades.parquet")

    # 2. 生成 OKX BookTicker 数据 (100条)
    # OKXBooktickerArrayReader 期望字段：timestamp/symbol/(local_timestamp 可选) + ask/bid 1..25 档
    ticker_df = pd.DataFrame({
        'timestamp': range(1000, 101000, 1000),
        'symbol': 'BTC-USDT',
        'local_timestamp': range(1000, 101000, 1000),
        'bid_price_1': [49999.0 + i * 0.1 for i in range(100)],
        'bid_amount_1': 1.0,
        'ask_price_1': [50001.0 + i * 0.1 for i in range(100)],
        'ask_amount_1': 1.0,
    })
    pq.write_table(pa.Table.from_pandas(ticker_df, preserve_index=False), "./data/bookTicker.parquet")
    print("[Demo] Dummy parquet files generated in ./data/")

# ==============================================================================
# 1. 策略定义
# ==============================================================================
class HelloworldStrategy(Strategy):
    def __init__(self, account):
        # 必须调用父类初始化并传入账户对象
        super().__init__(account)
        self.sent = False

    def start(self, engine):
        # 如果重写了 start，必须调用父类 start 以绑定 event_engine
        super().start(engine)
        # 订阅你关心的行情事件
        engine.register(OKXBookticker, self.on_bookticker)
        print("[Strategy] Engine attached.")

    def on_bookticker(self, event: OKXBookticker):
        # 简单的触发逻辑：收到第一条盘口后发送一个限价单
        if not self.sent:
            print(f"[Strategy] Bookticker received: {event.symbol} ts={event.timestamp}")
            
            # 使用工厂方法创建订单：方向由 quantity 正负决定（+买 / -卖）
            order = Order.create_limit(symbol="BTC-USDT", quantity=0.01, price=40000.0)
            
            # 使用父类提供的 send_order 接口
            self.send_order(order)
            self.sent = True
            print("[Strategy] Limit Order Sent!")

# ==============================================================================
# 2. 主程序
# ==============================================================================
if __name__ == "__main__":
    # 生成数据
    generate_dummy_data()

    symbol = "BTC-USDT"
    trades_path = "./data/trades.parquet"
    ticker_path = "./data/bookTicker.parquet"

    # --------------------------------------------------------------------------
    # [A] 数据加载配置 (High Performance Mode)
    # --------------------------------------------------------------------------
    # 1. 定义 Dataset: 开启 mode='batch'，只负责读取 DataFrame，不负责生成 Event
    trades_ds = ParquetDataset(trades_path, mode='batch')
    ticker_ds = ParquetDataset(ticker_path, mode='batch')

    # 2. 使用交易所专用 Reader（Cython + numpy 视图）把 DataFrame batch 转成 Event 流
    #    相比 Python 层逐条 yield，这条路径通常更快、更省内存。
    print("[Init] Loading data with OKX ArrayReader accelerator...")

    ticker_reader = OKXBooktickerArrayReader(ticker_ds)
    trades_reader = OKXTradesArrayReader(trades_ds)

    # 3. 合并数据流：多路归并后输出单一按时间排序的 Event 流
    ds = MergedDataset([ticker_reader, trades_reader])

    # --------------------------------------------------------------------------
    # [B] 引擎与延迟总线配置
    # --------------------------------------------------------------------------
    # 1. 定义延迟模型: 模拟 10ms 的固定光纤延迟
    latency_model = FixedDelayModel(delay=10000) # 单位: us (假设系统时间单位为us)

    # 2. 创建双向延迟总线
    #    Server -> Client (行情/回报延迟)
    bus_s2c = DelayBus(latency_model)
    #    Client -> Server (下单/撤单延迟)
    bus_c2s = DelayBus(latency_model)

    # 3. 初始化回测引擎 (传入 C++ 类型的 DelayBus)
    engine = BacktestEngine(
        dataset=ds,
        server2client_delaybus=bus_s2c,
        client2server_delaybus=bus_c2s,
    )

    # --------------------------------------------------------------------------
    # [C] 组件装配
    # --------------------------------------------------------------------------
    # === Server 端 (模拟交易所) ===
    engine.add_component(OKXMatcher(symbol), is_server=True)   # 撮合引擎
    server_acc = OKXAccount(initial_balance=100000.0)
    engine.add_component(server_acc, is_server=True)     # 交易所账户

    # === Client 端 (模拟本地策略) ===
    client_acc = OKXAccount(initial_balance=100000.0)
    engine.add_component(client_acc, is_server=False)    # 本地影子账户
    
    # 策略通常持有 client_account 的引用以查询资金/持仓
    strategy = HelloworldStrategy(client_acc)
    engine.add_component(strategy, is_server=False)      # 用户策略

    # --------------------------------------------------------------------------
    # [D] 运行
    # --------------------------------------------------------------------------
    print("[Run] Start backtest...")
    start_t = time.time()
    engine.run()
    print(f"[Run] Backtest finished in {time.time() - start_t:.4f}s")
```

<a id="data-prep"></a>
## 📂 数据准备 (Data Preparation)

HftBacktest 不强制绑定特定的数据源格式（如 CSV 或特定 DB），而是通过 `Dataset`/`DataReader` 抽象来适配任意数据源。

当前项目里常用两条接入路径：

1. **Event 模式（简单/通用）**：`ParquetDataset(mode='event')` 直接把表格列映射成 `Event`（或其子类）并逐条迭代输出。
2. **Batch + ArrayReader 模式（推荐/高性能）**：`ParquetDataset(mode='batch')` 先逐批输出 `pandas.DataFrame`，再用交易所专用 `*ArrayReader` 以 numpy 视图快速构造 `Event` 流。

Event 模式示例（把 Parquet 行映射为 `OKXTrades` 事件流）：

```python
from hft_backtest import ParquetDataset
from hft_backtest.okx.event import OKXTrades

trades_stream = ParquetDataset(
    "./data/trades.parquet",
    mode="event",
    event_type=OKXTrades,
    columns=["timestamp", "symbol", "trade_id", "price", "size", "side"],
    transform=lambda df: df.rename(columns={"created_time": "timestamp", "instrument_name": "symbol"}),
)
```

### 1. 自定义 Dataset（事件流 / 批流）

你只需提供一个可迭代对象：

- **Event 模式**：`yield hft_backtest.event.Event`（或子类，如 `OKXTrades/OKXBookticker`）
- **Batch 模式**：`yield pandas.DataFrame`

### 2. 时间戳与单位（强制一致）

框架内部依赖 `Event.timestamp` 做排序与时间推进，因此：

- 所有数据流必须使用 **同一时间单位**（例如统一用微秒 `us` 或纳秒 `ns`）。
- 每个单独数据源建议按时间 **非递减** 输出（否则多路归并与引擎推进会出现“回拨”）。

### 3. 多数据流合并 (MergedDataset)

`MergedDataset` 会把多个 **可迭代的 Event 流** 按时间戳做多路归并，输出单一事件流：

```python
# 自动按时间顺序合并多个 Event 流
ds = MergedDataset([ticker_stream, trades_stream])
```

### 4. OKX 数据推荐接入方式（Batch + ArrayReader）

OKX 的 `OKXBookticker` 字段较多（1..25 档），推荐用 batch 模式：

```python
from hft_backtest import ParquetDataset, MergedDataset
from hft_backtest.okx.reader import OKXBooktickerArrayReader, OKXTradesArrayReader

ticker_ds = ParquetDataset("./data/bookTicker.parquet", mode="batch")
trades_ds = ParquetDataset("./data/trades.parquet", mode="batch")

ticker_stream = OKXBooktickerArrayReader(ticker_ds)
trades_stream = OKXTradesArrayReader(trades_ds)

ds = MergedDataset([ticker_stream, trades_stream])
```

---

## 📊 性能优化 (Performance)

本框架针对高频回测场景进行了深度优化：

* **内存管理**: 读取 Parquet 文件时建议使用 `iter_batches`，结合 `yield` 生成器模式，即使回放 100GB 的数据，内存占用也能保持在较低水平（通常 < 2GB）。
* **Cython 加速**: 关键路径上的对象（如 `Order`, `Event`, `Timer`）均由 Cython 实现，避免了频繁的 Python 对象创建销毁开销。
* **无锁设计**: 内部事件循环采用单线程模型，规避了多线程锁竞争，适合 CPU 密集型的回测计算。

---

## 🛠️ 常见问题 (FAQ)

**Q: 为什么报错 `AttributeError: type object 'hft_backtest.event.Event' has no attribute ...`?**
A: 请检查您的 Python 版本。本框架目前**不支持 Python 3.11 及以上版本**，因为 Cython 在新版 Python 中的底层对象结构有变更。请降级到 Python 3.10 或 3.9。

**Q: 可以在 Windows 上运行吗？**
A: 可以。但编译时需要安装 "Microsoft C++ Build Tools"。建议在 WSL2 (Linux 子系统) 中运行以获得最佳性能。

---

## 📄 License

MIT License

Copyright (c) 2024 Tan yue
