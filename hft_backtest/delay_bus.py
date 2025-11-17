from event_engine import Event, EventEngine

class DelayBus:
    """
    监听源事件引擎的消息
    将源自源事件引擎的消息滞后一定时间后再发布到目标事件引擎

    使用时间戳作为dt的表达, 避免使用datetime类型带来的计算开销
    高频交易系统消息延迟总线的业务场景是高put, 低update, 使用朴素列表实现比较合理
    加入了很多断言方便bug调试, 实际使用中请关闭以释放性能
    """
    def __init__(
        self,
        source_engine:EventEngine,
        target_engine:EventEngine,
        delay:int = 100,
    ):
        self.delay = delay
        self.source_engine = source_engine
        self.target_engine = target_engine
        self.event_queue = []
        # 注册监听源事件引擎
        self.source_engine.register(Event, self.on_event)

    def on_event(self, event:Event):
        assert isinstance(event, Event)
        # 仅接收源事件引擎的事件
        if event.source == id(self.source_engine):
            self.event_queue.append((event, event.timestamp + self.delay))
        # 推送可用事件到目标事件引擎
        remain = []
        for event, ready_time in self.event_queue:
            if ready_time <= self.source_engine.timestamp:
                self.target_engine.put(event)
            else:
                remain.append((event, ready_time))
        self.event_queue = remain

if __name__ == "__main__":
    source_engine = EventEngine()
    target_engine = EventEngine()
    source_engine.register(Event, lambda e: print(f"Source engine received {e}"))
    target_engine.register(Event, lambda e: print(f"Target engine received {e}"))
    delay_bus = DelayBus(source_engine, target_engine, delay=100)
    for i in range(5):
        event = Event(timestamp=i * 50)
        source_engine.put(event)