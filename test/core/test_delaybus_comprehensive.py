import pytest
from hft_backtest import Event, EventEngine
from hft_backtest.delaybus import DelayBus, LatencyModel, FixedDelayModel

# --- 辅助类：用于测试乱序到达的动态延迟模型 ---
class MockVariableLatency(LatencyModel):
    """
    模拟网络抖动：允许为每一个事件指定不同的延迟。
    这用于验证 DelayBus 的最小堆排序能力。
    """
    def __init__(self, delays: list[int]):
        self.delays = delays
        self.index = 0

    def get_delay(self, event: Event) -> int:
        if self.index < len(self.delays):
            d = self.delays[self.index]
            self.index += 1
            return d
        return 1000 # Default

class TestDelayBusComprehensive:

    @pytest.fixture
    def engines(self):
        source = EventEngine()
        target = EventEngine()
        return source, target

    def test_basic_fixed_delay(self, engines):
        """测试 1: 基础固定延迟逻辑"""
        source, target = engines
        
        # 延迟 100ns
        bus = DelayBus(FixedDelayModel(100))
        bus.set_target_engine(target)
        bus.start(source)
        
        received = []
        target.register(Event, received.append)
        
        # T=10 发送
        e1 = Event(timestamp=10)
        e1.source = source._id # 模拟 Source 发出
        source.put(e1)
        
        # 预期到达时间: 10 + 100 = 110
        assert bus.next_timestamp == 110
        
        # T=100 时处理，应该收不到
        bus.process_until(100)
        assert len(received) == 0
        
        # T=110 时处理，应该收到
        bus.process_until(110)
        assert len(received) == 1
        assert received[0].timestamp == e1.timestamp
        assert received[0].source == e1.source
        assert received[0].producer == e1.producer
        assert target.timestamp == 110  # 目标时间应被推进

    def test_heap_ordering_jitter(self, engines):
        """
        测试 2: [核心] 验证最小堆排序 (Jitter 模拟)
        场景：
        Event A: T=10, Delay=100 -> Arrival=110
        Event B: T=20, Delay=10  -> Arrival=30
        
        虽然 Event A 先发，但 Event B 应该先到。
        """
        source, target = engines
        
        # 使用自定义模型：第一次调用延迟100，第二次延迟10
        model = MockVariableLatency([100, 10])
        bus = DelayBus(model)
        bus.set_target_engine(target)
        bus.start(source)
        
        received = []
        target.register(Event, received.append)
        
        # 发送 Event A
        ea = Event(timestamp=10); ea.source = source._id
        source.put(ea)
        
        # 发送 Event B
        eb = Event(timestamp=20); eb.source = source._id
        source.put(eb)
        
        # 此时堆里应该有两个事件。
        # 最早触发的应该是 Event B (20+10=30)，而不是 Event A (10+100=110)
        assert bus.next_timestamp == 30
        
        # 处理到 T=50
        bus.process_until(50)
        
        # 应该只收到了 Event B
        assert len(received) == 1
        assert received[0].timestamp == eb.timestamp
        assert received[0].source == eb.source
        assert received[0].producer == eb.producer
        assert target.timestamp == 30
        
        # 处理到 T=120
        bus.process_until(120)
        
        # 现在收到了 Event A
        assert len(received) == 2
        assert received[1].timestamp == ea.timestamp
        assert received[1].source == ea.source
        assert received[1].producer == ea.producer
        assert target.timestamp == 110

    def test_source_filtering(self, engines):
        """测试 3: 多源过滤，防止偷听其他引擎的事件"""
        source1, target = engines
        source2 = EventEngine() # 干扰源
        
        bus = DelayBus(FixedDelayModel(10))
        bus.set_target_engine(target)
        bus.start(source1) # 只监听 source1
        
        received = []
        target.register(Event, received.append)
        
        # Source 1 发送 (应该被处理)
        e1 = Event(timestamp=100); e1.source = source1._id
        source1.put(e1)
        
        # Source 2 发送 (应该被忽略)
        e2 = Event(timestamp=100); e2.source = source2._id
        # 注意：这里我们模拟把 source2 的事件塞进 source1 的总线（虽然在 EventEngine 内部这通常不会发生，
        # 但我们要测试 DelayBus 的 .source 过滤逻辑是否生效）
        bus.on_event(e2) 
        
        # 检查堆
        # e1 (100+10=110) 应该在堆里
        assert bus.next_timestamp == 110
        
        bus.process_until(200)
        
        # 结果：只收到 e1，e2 被丢弃
        assert len(received) == 1
        assert received[0].timestamp == e1.timestamp
        assert received[0].source == e1.source
        assert received[0].producer == e1.producer

    def test_target_time_sync(self, engines):
        """测试 4: 目标引擎时间同步逻辑"""
        source, target = engines
        bus = DelayBus(FixedDelayModel(50))
        bus.set_target_engine(target)
        bus.start(source)
        
        # 目标引擎当前时间落后
        target.timestamp = 100
        
        # 事件到达时间: 200 + 50 = 250
        e = Event(timestamp=200); e.source = source._id
        source.put(e)
        
        # 驱动总线
        bus.process_until(300)
        
        # 目标引擎时间应该被强制推到 250 (事件到达时刻)
        assert target.timestamp == 250

    def test_zero_delay_edge_case(self, engines):
        """测试 5: 零延迟边界情况"""
        source, target = engines
        bus = DelayBus(FixedDelayModel(0)) # 0 延迟
        bus.set_target_engine(target)
        bus.start(source)
        
        target_events = []
        target.register(Event, target_events.append)
        
        e = Event(timestamp=12345); e.source = source._id
        source.put(e)
        
        # 应该立即就绪
        assert bus.next_timestamp == 12345
        
        bus.process_until(12345)
        assert len(target_events) == 1
        assert target_events[0].timestamp == 12345

    def test_batch_processing(self, engines):
        """测试 6: 批量出堆能力"""
        source, target = engines
        bus = DelayBus(FixedDelayModel(10))
        bus.set_target_engine(target)
        bus.start(source)
        
        rec = []
        target.register(Event, rec.append)
        
        # 放入 3 个事件
        for t in [10, 20, 30]:
            e = Event(timestamp=t); e.source = source._id
            source.put(e)
            
        # 预期到达: 20, 30, 40
        
        # 一次性处理到 100
        bus.process_until(100)
        
        assert len(rec) == 3
        # 顺序应该正确
        assert [e.timestamp for e in rec] == [10, 20, 30]
        # 目标时间应停留在最后一个事件的到达时间
        assert target.timestamp == 40 # 30 + 10

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))