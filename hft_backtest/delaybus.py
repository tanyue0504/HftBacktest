from collections import deque
from hft_backtest import Event, EventEngine
import math

class DelayBus:
    def __init__(
        self,
        source_engine: EventEngine,
        target_engine: EventEngine,
        delay: int = 100,
    ):
        self.delay = delay
        self.source_engine = source_engine
        self.target_engine = target_engine
        # 存储 (event, ready_time)
        self.event_queue: deque[tuple[Event, int]] = deque()
        # 注册监听
        self.source_engine.global_register(self.on_event, is_senior=False)

    def on_event(self, event: Event):
        # 仅处理源引擎产生的事件
        if event.source == self.source_engine._id:
            # 计算该事件应该在什么时候到达目标引擎
            ready_time = event.timestamp + self.delay
            self.event_queue.append((event, ready_time))

    @property
    def next_timestamp(self) -> int:
        """返回队列中最早待处理事件的时间，如果没有则返回无穷大"""
        if not self.event_queue:
            return math.inf
        # 队列是按时间顺序进入的（假设源引擎时间单调递增），所以队头就是最早的
        return self.event_queue[0][1]

    def process_until(self, timestamp: int):
        """
        处理所有 ready_time <= timestamp 的事件
        将它们推送到 target_engine
        """
        while self.event_queue:
            # 偷看队头
            event, ready_time = self.event_queue[0]
            
            if ready_time > timestamp:
                break
            
            # 弹出并处理
            self.event_queue.popleft()
            
            # 【关键】在推送前，必须先把目标引擎的时间更新到 ready_time
            # 否则目标引擎可能会觉得“时间倒流”或者“时间没变”
            if self.target_engine.timestamp < ready_time:
                self.target_engine.timestamp = ready_time
                
            self.target_engine.put(event)

if __name__ == "__main__":
    source_engine = EventEngine()
    target_engine = EventEngine()
    source_engine.register(Event, lambda e: print(f"Source engine received {e}"))
    target_engine.register(Event, lambda e: print(f"Target engine received {e}"))
    delay_bus1 = DelayBus(source_engine, target_engine, delay=100)
    delay_bus2 = DelayBus(target_engine, source_engine, delay=100)
    for i in range(5):
        event = Event(timestamp= source_engine.timestamp + 50)
        source_engine.put(event)
    for i in range(5):
        event = Event(timestamp= target_engine.timestamp + 50)
        target_engine.put(event)