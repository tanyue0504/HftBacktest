import math
from itertools import chain

from hft_backtest import Dataset, Component, EventEngine, DelayBus, Timer

class BacktestEngine:
    """
    事件驱动回测引擎 (Python 逻辑重构版)
    集成 Timer 发生器与 DelayBus 管理
    """
    def __init__(
        self,
        dataset: Dataset, 
        server2client_delaybus: DelayBus,
        client2server_delaybus: DelayBus,
        timer_interval: int = 1000,  # 定时器间隔 (ms)
    ):
        # 初始化内部变量
        self.server_engine = EventEngine()
        self.client_engine = EventEngine()
        
        self.server_components: list[Component] = []
        self.client_components: list[Component] = []

        # 保存参数
        self.dataset = dataset
        self.timer_interval = timer_interval
        
        self.server2client_bus = server2client_delaybus
        self.client2server_bus = client2server_delaybus

        # 【核心修改】在此处进行"接线" (Wiring)
        # ServerBus 负责把 Server 的事件搬运给 Client
        self.server2client_bus.set_target_engine(self.client_engine)
        self.client2server_bus.set_target_engine(self.server_engine)

        # 注册组件：DelayBus 需要监听它的"源头"
        # server2client 监听 Server，所以它是 Server 的组件
        self.add_component(self.server2client_bus, is_server=True)
        # client2server 监听 Client，所以它是 Client 的组件
        self.add_component(self.client2server_bus, is_server=False)

    def add_component(self, component: Component, is_server: bool):
        if is_server:
            self.server_components.append(component)
        else:
            self.client_components.append(component)
        
    def run(self):
        with self:
            # 获取数据迭代器
            data_iterator = iter(self.dataset)
            current_data = next(data_iterator, None)

            next_timer = current_data.timestamp

            while current_data is not None:
                # 1. 获取四个时间点的最小值（事件竞价）：
                #    A. 下一条行情数据
                #    B. Server->Client 延迟消息
                #    C. Client->Server 延迟消息
                #    D. 下一次定时器触发 (Timer)
                
                t_data = current_data.timestamp
                t_s2c = self.server2client_bus.next_timestamp
                t_c2s = self.client2server_bus.next_timestamp
                
                # 找出最小时间戳，决定先处理谁
                min_t = min(t_data, t_s2c, t_c2s, next_timer)
                
                # 2. 事件处理 (优先级策略：DelayBus > Timer > Data)
                
                # 情况 A: 处理延迟消息 (Server -> Client)
                # 必须使用 <= 以处理同一毫秒内的事件
                if t_s2c <= min_t:
                    self.server2client_bus.process_until(t_s2c)
                    continue
                
                # 情况 B: 处理延迟消息 (Client -> Server)
                if t_c2s <= min_t:
                    self.client2server_bus.process_until(t_c2s)
                    continue

                # 情况 C: 处理 Timer
                if next_timer <= min_t:
                    self.client_engine.put(Timer(next_timer))
                    next_timer += self.timer_interval
                    continue

                # 情况 D: 处理行情数据
                if t_data == min_t:
                    # 数据通常先到达 Server (模拟交易所撮合)
                    self.server_engine.put(current_data)
                    current_data = next(data_iterator, None)
            
            # --- 数据耗尽后的收尾 ---
            # 处理还在路上的延迟消息 (防止最后几笔回报丢失)
            while True:
                t_s2c = self.server2client_bus.next_timestamp
                t_c2s = self.client2server_bus.next_timestamp
                
                if t_s2c == math.inf and t_c2s == math.inf:
                    break
                
                # 谁的时间早处理谁
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