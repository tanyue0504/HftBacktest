from hft_backtest import Dataset, MergedDataset, Component, EventEngine, DelayBus

from itertools import chain
import math

class BacktestEngine:
    """
    单事件引擎本质上是双事件引擎在delay=0时的特例
    """
    def __init__(
        self,
        datasets: list[Dataset],
        delay:int = 0, # unit: ms
        start_timestamp: int = None,
        end_timestamp: int = None,
    ):
        self.dataset = MergedDataset(*datasets)
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()
        self.server_components: list[Component] = []
        self.client_components: list[Component] = []
        self.server2client_bus = DelayBus(
            self.server_engine,
            self.client_engine,
            delay
        )
        self.client2server_bus = DelayBus(
            self.client_engine,
            self.server_engine,
            delay
        )
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp


    def add_component(self, component:Component, is_server: bool):
        if is_server:
            self.server_components.append(component)
        else:
            self.client_components.append(component)
        
    def run(self):
        with self:
            # 获取数据迭代器
            data_iterator = iter(self.dataset)
            current_data = next(data_iterator, None)

            while current_data is not None:
                # 1. 获取三个时间点的最小值：
                #    A. 下一条行情数据的时间
                #    B. Server->Client 总线最早消息的时间
                #    C. Client->Server 总线最早消息的时间
                
                t_data = current_data.timestamp
                t_s2c = self.server2client_bus.next_timestamp
                t_c2s = self.client2server_bus.next_timestamp
                
                min_t = min(t_data, t_s2c, t_c2s)
                # 时光回放
                if self.start_timestamp is not None and min_t < self.start_timestamp:
                    continue
                if self.end_timestamp is not None and min_t > self.end_timestamp:
                    break

                # 2. 谁的时间到了，就处理谁
                
                # 情况 A: 延迟消息先到（或同时到），先处理延迟消息
                # 注意：优先处理 Bus 消息，防止同一毫秒内，策略先收到行情再收到之前的回报，导致乱序
                if t_s2c <= min_t:
                    self.server2client_bus.process_until(t_s2c)
                    continue # 处理完回到循环头部，重新评估
                
                if t_c2s <= min_t:
                    self.client2server_bus.process_until(t_c2s)
                    continue

                # 情况 B: 行情数据时间到了
                if t_data == min_t:
                    self.server_engine.put(current_data)
                    # 取下一条数据
                    current_data = next(data_iterator, None)
            
            # 数据耗尽后，处理剩余的延迟消息
            while True:
                t_s2c = self.server2client_bus.next_timestamp
                t_c2s = self.client2server_bus.next_timestamp
                if t_s2c == math.inf and t_c2s == math.inf:
                    break
                
                if t_s2c <= t_c2s:
                     self.server2client_bus.process_until(t_s2c)
                else:
                     self.client2server_bus.process_until(t_c2s)

    def __enter__(self):
        for component in self.server_components:
            component.start(self.server_engine)
        for component in self.client_components:
            component.start(self.client_engine)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        for component in chain(self.server_components, self.client_components):
            component.stop()
        return False