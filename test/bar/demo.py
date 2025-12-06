"""
测试框架在中低频数据下的表现

数据
k线数据 bar
资金费率事件 funding_rate
溢价率事件 premium_rate

测试内容
backtest组件组装测试
backtest数据推送测试
event_engine事件推送测试
strategy数据接收和执行测试
barmathcer撮合测试
account接口测试
recorder数据记录测试

测试结果
"""

from hft_backtest.low_freq import *
from hft_backtest import BacktestEngine, Strategy, Event, EventEngine, Data

class DemoStrategy(Strategy):
    def __init__(self):
        super().__init__()

    def start(self, engine: EventEngine):
        self.event_engine = engine
    
    def stop(self):
        return super().stop()
    
    def on_data(self, data: Data):
        print(f"Received bar: {data}")

def run_demo():
    # 初始化事件引擎
    event_engine = EventEngine()
    
    # 初始化回测引擎
    backtest_engine = BacktestEngine(event_engine)
    
    # 注册策略
    strategy = DemoStrategy()
    backtest_engine.register_strategy(strategy)
    
    # 加载中低频数据
    bar_data = load_bar_data("path_to_bar_data.csv")
    backtest_engine.load_data(bar_data)
    
    # 启动回测
    backtest_engine.start_backtest()
    
    # 停止策略
    strategy.stop()
    
    # 输出结果
    print("Backtest completed.")

if __name__ == "__main__":
    run_demo()