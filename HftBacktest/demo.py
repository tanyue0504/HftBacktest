"""
demo.py
既是框架测试，也是使用示例

核心使用流程
1. 自定义数据集合，有多少数据源就定义多少个 Dataset 子类
2. 定义策略 Strategy 子类
3. 构建 BacktestEngine，传入数据集列表和策略类
4. 运行 BacktestEngine.run() 开始回测

请注意
最核心的是撮合引擎
而撮合引擎与数据息息相关
目前实现了一个基于binance bookticker & aggTrades/Trades数据的撮合引擎
"""
