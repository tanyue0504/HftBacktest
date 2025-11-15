# HFT Backtest Framework - Design Document

## 问题陈述 (Problem Statement)

在设计高频回测系统时，我们面临以下核心问题：

1. **数据源的灵活性**：数据源由用户自定义Dataset实现，如果有多个可以用MergedDataset来聚合
2. **绩效计算的困境**：在Account的设计中，如果不指定数据源，绩效计算是不可能的，只能交给用户来实现
3. **数据访问的必要性**：如果让用户自定义PerformanceCalculator，那么是不是需要把数据也推送给它？否则只能查询持仓会导致计算不准确

## 设计方案 (Design Solution)

### 核心思想：数据推送架构 (Data Push Architecture)

本框架采用**主动数据推送**的设计模式，而不是传统的"查询"模式。这样做的好处是：

1. **解耦数据源**：PerformanceCalculator 不需要知道数据来自哪里
2. **确保准确性**：数据和持仓信息同步推送，避免时间差导致的计算错误
3. **灵活性**：用户可以自由实现自己的性能指标计算

### 架构图

```
┌─────────────┐
│  Dataset 1  │─┐
└─────────────┘ │
┌─────────────┐ │     ┌──────────────┐
│  Dataset 2  │─┼────▶│MergedDataset │
└─────────────┘ │     └──────┬───────┘
┌─────────────┐ │            │
│  Dataset 3  │─┘            │ MarketData流
└─────────────┘              │
                             ▼
                      ┌──────────────┐
                      │   Account    │
                      │              │
                      │ • execute_   │
                      │   order()    │
                      │ • on_market_ │
                      │   data()     │◀─── 关键：数据推送
                      └──────┬───────┘
                             │
                推送: data + position_info
                             │
                             ▼
                 ┌─────────────────────────┐
                 │ PerformanceCalculator   │
                 │                         │
                 │ • on_market_data()      │
                 │ • on_trade()            │
                 │ • get_metrics()         │
                 └─────────────────────────┘
```

### 关键设计点

#### 1. Account.on_market_data() 方法

这是整个架构的核心：

```python
def on_market_data(self, data: MarketData):
    """
    Process market data update.
    
    This method pushes market data to the PerformanceCalculator, enabling
    accurate performance tracking without requiring the calculator to query positions.
    """
    if self.performance_calculator:
        # Get current position for this symbol
        position = self.positions.get(data.symbol)
        position_quantity = position.quantity if position else 0.0
        position_avg_price = position.avg_price if position else 0.0
        
        # Push data to performance calculator
        self.performance_calculator.on_market_data(
            data, 
            position_quantity, 
            position_avg_price,
            self.cash
        )
```

**重点**：Account 在收到市场数据时，会：
1. 获取当前该标的的持仓信息
2. 将市场数据、持仓数量、持仓均价、现金余额一起推送给 PerformanceCalculator
3. 这样 PerformanceCalculator 就能准确计算当前的权益和绩效

#### 2. PerformanceCalculator 接口

```python
class PerformanceCalculator(ABC):
    @abstractmethod
    def on_market_data(self, data: MarketData, position_quantity: float, 
                      position_avg_price: float, cash: float):
        """
        Called when market data is updated.
        
        This method receives both market data and current position information,
        enabling accurate performance tracking without requiring position queries.
        """
        pass
```

**优势**：
- 不需要查询持仓（避免并发问题）
- 数据和持仓状态同步（避免时间差）
- 可以计算任意自定义指标

#### 3. MergedDataset 的实现

使用堆排序高效合并多个有序数据流：

```python
def __iter__(self):
    # Create iterators for all datasets
    self._iterators = [iter(dataset) for dataset in self.datasets]
    
    # Initialize heap with first element from each iterator
    heap = []
    for idx, it in enumerate(self._iterators):
        try:
            data = next(it)
            heapq.heappush(heap, (data.timestamp, idx, data))
        except StopIteration:
            pass
    
    # Merge streams using heap
    while heap:
        timestamp, idx, data = heapq.heappop(heap)
        yield data
        
        # Try to get next element from the same iterator
        try:
            next_data = next(self._iterators[idx])
            heapq.heappush(heap, (next_data.timestamp, idx, next_data))
        except StopIteration:
            pass
```

**时间复杂度**：O(N log K)，其中 N 是总数据量，K 是数据源数量

## 使用示例

### 完整的回测流程

```python
# 1. 创建数据源
dataset1 = MyDataset('AAPL', [...])
dataset2 = MyDataset('GOOGL', [...])

# 2. 合并数据源
merged = MergedDataset([dataset1, dataset2])

# 3. 创建性能计算器
perf_calc = SimplePerformanceCalculator()

# 4. 创建账户（关联性能计算器）
account = Account(initial_capital=100000.0, 
                 performance_calculator=perf_calc)

# 5. 回测循环
for data in merged:
    # 推送数据到账户（自动更新性能）
    account.on_market_data(data)
    
    # 执行交易策略
    if buy_signal(data):
        account.execute_order(data.symbol, 10, data.price)
    elif sell_signal(data):
        account.execute_order(data.symbol, -10, data.price)

# 6. 获取性能指标
metrics = perf_calc.get_metrics()
print(f"Total Return: {metrics['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
```

### 自定义性能计算器

```python
class MyCustomPerformanceCalculator(PerformanceCalculator):
    def __init__(self):
        self.custom_metrics = []
    
    def initialize(self, initial_capital: float):
        self.capital = initial_capital
    
    def on_market_data(self, data, position_quantity, position_avg_price, cash):
        # 计算自定义指标
        equity = cash + position_quantity * data.price
        custom_value = calculate_my_metric(equity, data)
        self.custom_metrics.append(custom_value)
    
    def on_trade(self, symbol, quantity, price, commission, cash):
        # 记录交易信息
        pass
    
    def get_metrics(self):
        return {
            'my_custom_metric': sum(self.custom_metrics),
            'average_custom': sum(self.custom_metrics) / len(self.custom_metrics)
        }
```

## 性能优化

### 内存优化

SimplePerformanceCalculator 默认记录完整的权益曲线，对于大规模回测可能消耗较多内存。用户可以：

1. 只记录关键时间点
2. 使用滑动窗口计算指标
3. 定期持久化数据到文件

### 计算优化

MergedDataset 使用堆排序，时间复杂度为 O(N log K)，对于大量数据源仍然高效。

## 扩展性

框架设计考虑了以下扩展场景：

1. **多账户**：可以创建多个 Account，每个使用不同的策略
2. **实时交易**：Dataset 可以连接实时数据源
3. **复杂订单**：可以扩展 Account 支持限价单、止损单等
4. **风险管理**：可以在 Account 中添加风控检查
5. **事件驱动**：可以添加 EventBus 支持更复杂的事件处理

## 测试

框架包含完整的单元测试：

- `test_dataset.py`: 测试数据源和合并逻辑
- `test_account.py`: 测试账户和持仓管理
- `test_performance.py`: 测试性能计算

运行测试：
```bash
python -m unittest discover tests -v
```

## 总结

本框架通过**数据推送架构**优雅地解决了高频回测中的核心问题：

1. ✅ 数据源灵活可扩展（用户自定义 Dataset）
2. ✅ 多数据源自动合并（MergedDataset）
3. ✅ 性能计算准确（数据和持仓同步推送）
4. ✅ 易于自定义（继承 PerformanceCalculator）

这个设计保证了框架的**简洁性、准确性和扩展性**，适合高频交易策略的回测需求。
