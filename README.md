# HftBacktest
用python写的简易高频回测框架

## 简介

HftBacktest 是一个简单但功能完整的高频交易回测框架，专注于解决实际回测中的常见问题。

## 核心设计理念

### 问题背景

在高频回测系统中，我们面临以下设计挑战：

1. **数据源的灵活性**：数据源应该由用户自定义实现，如果有多个数据源，可以用 MergedDataset 来聚合
2. **绩效计算问题**：在 Account 的设计中，如果不指定数据源，绩效计算是不可能的
3. **数据推送的必要性**：如果让用户自定义 PerformanceCalculator，必须把数据也推送给它，否则只能查询持仓会导致计算不准确

### 解决方案

本框架采用**数据推送模式**来解决上述问题：

1. **Dataset**: 抽象的数据源基类，用户可以继承实现自定义数据源
2. **MergedDataset**: 将多个数据源按时间顺序聚合
3. **Account**: 账户类，接收市场数据并主动推送给 PerformanceCalculator
4. **PerformanceCalculator**: 绩效计算器，接收数据推送和持仓信息，准确计算绩效

关键设计：**Account 在收到市场数据时，会自动将数据和当前持仓信息推送给 PerformanceCalculator**，这样 PerformanceCalculator 就能准确计算绩效，而不需要自己去查询持仓。

## 安装

```bash
pip install -e .
```

## 快速开始

### 1. 创建自定义数据源

```python
from hft_backtest import Dataset, MarketData

class MyDataset(Dataset):
    def __init__(self, data_points):
        self.data_points = data_points
    
    def __iter__(self):
        for timestamp, symbol, price, volume in self.data_points:
            yield MarketData(timestamp, symbol, price, volume)
    
    def reset(self):
        pass
```

### 2. 使用 MergedDataset 聚合多个数据源

```python
from hft_backtest import MergedDataset

dataset1 = MyDataset([...])
dataset2 = MyDataset([...])

# 自动按时间顺序合并
merged = MergedDataset([dataset1, dataset2])
```

### 3. 创建账户和绩效计算器

```python
from hft_backtest import Account, SimplePerformanceCalculator

# 创建绩效计算器
perf_calc = SimplePerformanceCalculator()

# 创建账户，关联绩效计算器
account = Account(initial_capital=100000.0, performance_calculator=perf_calc)
```

### 4. 运行回测

```python
for data in merged:
    # 推送市场数据（自动更新绩效）
    account.on_market_data(data)
    
    # 执行交易策略
    if some_condition:
        account.execute_order(data.symbol, quantity=10, price=data.price)

# 获取绩效指标
metrics = perf_calc.get_metrics()
print(metrics)
```

## 完整示例

查看 `examples/simple_backtest.py` 获取完整的示例代码。

运行示例：

```bash
python examples/simple_backtest.py
```

## 核心组件

### Dataset

抽象基类，定义数据源接口：

- `__iter__()`: 按时间顺序迭代市场数据
- `reset()`: 重置数据源到开始位置

### MergedDataset

聚合多个数据源，按时间顺序输出：

- 使用堆排序高效合并多个有序流
- 自动处理不同数据源的时间对齐

### Account

管理账户状态和交易：

- `execute_order()`: 执行交易订单
- `on_market_data()`: 接收市场数据，**自动推送给 PerformanceCalculator**
- `get_equity()`: 计算总权益

### PerformanceCalculator

绩效计算器接口（抽象基类）：

- `initialize()`: 初始化起始资金
- `on_market_data()`: 接收市场数据和持仓信息
- `on_trade()`: 接收交易通知
- `get_metrics()`: 获取绩效指标

框架提供 `SimplePerformanceCalculator` 作为默认实现，计算：

- 总收益率
- 最大回撤
- 夏普比率
- 权益曲线
- 交易次数

## 自定义绩效计算器

```python
from hft_backtest import PerformanceCalculator

class MyPerformanceCalculator(PerformanceCalculator):
    def initialize(self, initial_capital):
        self.capital = initial_capital
    
    def on_market_data(self, data, position_quantity, position_avg_price, cash):
        # 收到市场数据和当前持仓信息
        # 可以准确计算当前绩效
        pass
    
    def on_trade(self, symbol, quantity, price, commission, cash):
        # 收到交易通知
        pass
    
    def get_metrics(self):
        return {'custom_metric': 123}
```

## 运行测试

```bash
python -m unittest discover tests
```

## 架构图

```
Dataset (用户自定义) ─┐
Dataset (用户自定义) ─┼─> MergedDataset ─> Account ─> PerformanceCalculator
Dataset (用户自定义) ─┘                       │              ↑
                                              │              │
                                              └──────────────┘
                                              数据推送（关键设计）
```

## 许可证

MIT License
