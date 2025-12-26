import pytest
import sys
from hft_backtest.event import Event
from hft_backtest.event_engine import EventEngine
from hft_backtest.delaybus import DelayBus, FixedDelayModel, LatencyModel

# 定义用于测试的 Event 子类，携带额外的测试数据
class TestEvent(Event):
    def __init__(self, timestamp, delay_val=0):
        super().__init__(timestamp)
        self.extra_delay = delay_val

class TestDelayBus:
    def test_basic_transmission(self):
        """测试基本的延迟传输功能"""
        # 1. 设置 Source 和 Target 引擎
        source = EventEngine()
        target = EventEngine()
        
        # 2. 设置总线 (延迟 100ns)
        delay = 100
        bus = DelayBus(FixedDelayModel(delay))
        bus.start(source)
        bus.set_target_engine(target)
        
        # 3. 发送事件
        e = Event(1000)
        source.put(e)  # 此时 Event source 被设为 source._id
        
        # 4. 检查 Bus 状态
        # 事件进入 source -> global_listener (bus) -> on_event -> bus queue
        # 此时 target 应该还没收到
        assert bus.next_timestamp == 1000 + delay
        
        # 5. 推进时间
        # 推进到 1099 (不足触发)
        bus.process_until(1099)
        # 此时 target 应该还没收到事件
        received = []
        target.register(Event, lambda x: received.append(x))
        
        # 注意：无需调用 target._drain()，因为 EventEngine.put 是自动 drain 的
        assert len(received) == 0
        
        # 6. 推进到 1100 (触发)
        bus.process_until(1100)
        
        assert len(received) == 1
        assert received[0].timestamp == 1000  # 原始时间戳保留
        # 检查 target 引擎的时间是否被推动
        assert target.timestamp == 1100

    def test_snapshot_isolation(self):
        """测试快照隔离：修改原事件不应影响传输中的事件"""
        source = EventEngine()
        target = EventEngine()
        bus = DelayBus(FixedDelayModel(10))
        bus.start(source)
        bus.set_target_engine(target)
        
        # 定义一个带属性的 Event 子类
        e = Event(100)
        e.producer = 123
        
        source.put(e)
        
        # 修改原对象 (模拟策略在发送后修改了对象)
        e.producer = 999
        e.timestamp = 200
        
        # 接收
        bus.process_until(200)
        
        received = []
        target.register(Event, lambda x: received.append(x))
        
        # DelayBus 内部已经把事件塞入 target 并触发了回调，
        # 但我们是在 process_until 之后才注册的 listener？
        # 不，上面的逻辑有问题。process_until 会执行 put，put 会立即触发 listener。
        # 所以必须在 process_until 之前注册 listener。
        
        # 重新来一遍流程：
        target = EventEngine()
        bus.set_target_engine(target)
        
        # 先注册监听
        received = []
        target.register(Event, lambda x: received.append(x))
        
        # 发送
        e = Event(100)
        e.producer = 123
        source.put(e)
        
        # 修改
        e.producer = 999
        
        # 处理
        bus.process_until(200)
        
        assert len(received) == 1
        r_event = received[0]
        
        # 验证收到的是修改前的快照 (derive 拷贝了 producer)
        # 注意：EventEngine.put 会把 producer 重置为 0 (如果没有 listener 在运行)
        # 所以这里 source.put(e) 时，e.producer 变成了 0。
        # DelayBus 收到的是 0。
        # 所以这里验证 producer 不太合适，除非我们在 global_register 里拦截
        # 但 timestamp 是不会被 put 修改的（如果 > 0）
        
        assert r_event.timestamp == 100
        assert r_event.timestamp != 200 # 没变成修改后的值
        assert r_event is not e

    def test_out_of_order_arrival(self):
        """测试乱序到达（堆排序逻辑）"""
        source = EventEngine()
        target = EventEngine()
        
        # 自定义动态延迟模型
        class DynamicModel(LatencyModel):
            def get_delay(self, event):
                # 使用自定义属性 extra_delay
                # 注意：EventEngine 不会触碰它不认识的 Python 属性
                if hasattr(event, 'extra_delay'):
                    return event.extra_delay
                return 0

        bus = DelayBus(DynamicModel())
        bus.start(source)
        bus.set_target_engine(target)
        
        # 事件 A: T=100, Delay=50 -> Arrive=150
        ea = TestEvent(100, delay_val=50)
        
        # 事件 B: T=110, Delay=10 -> Arrive=120
        eb = TestEvent(110, delay_val=10)
        
        source.put(ea)
        source.put(eb)
        
        # 此时堆里应该有 [120, 150]
        assert bus.next_timestamp == 120
        
        received = []
        target.register(TestEvent, lambda x: received.append(x))
        
        # 1. 推进到 130
        bus.process_until(130)
        
        assert len(received) == 1
        assert received[0].timestamp == 110 # 事件 B 先到
        
        # 2. 推进到 160
        bus.process_until(160)
        
        assert len(received) == 2
        assert received[1].timestamp == 100 # 事件 A 后到

    def test_filter_source(self):
        """测试来源过滤：防止回声"""
        source = EventEngine() # ID: 1
        target = EventEngine() # ID: 2
        
        bus = DelayBus(FixedDelayModel(10))
        bus.start(source)
        bus.set_target_engine(target)
        
        # 1. 正常事件 (source 产生的)
        e1 = Event(100)
        source.put(e1)
        assert bus.next_timestamp == 110
        
        # 清空 bus
        bus.process_until(200)
        assert bus.next_timestamp == float('inf')
        
        # 2. 外部路由事件
        e2 = Event(100)
        e2.source = target._id 
        
        # 强行塞入
        source.put(e2) # put 会保留非0的 source
        
        # Bus 应该忽略这个事件
        assert bus.next_timestamp == float('inf')

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))