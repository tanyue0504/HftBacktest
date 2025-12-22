import pytest
from hft_backtest import Event, Component, EventEngine, Dataset
from hft_backtest.backtest import BacktestEngine
from hft_backtest.delaybus import DelayBus, FixedDelayModel
from hft_backtest.timer import Timer

# --- 辅助类 ---

class ListDataset(Dataset):
    """基于列表的简单数据集"""
    def __init__(self, events):
        self.events = events
        
    def __iter__(self):
        return iter(self.events)

class EventCollector(Component):
    """用于收集事件的组件，方便断言"""
    def __init__(self):
        # 存储格式: (Arrival_Time, Event_Object, Generation_Time)
        self.records = []
        self.engine = None
        
    def start(self, engine: EventEngine):
        self.engine = engine
        # 监听所有事件
        engine.global_register(self.on_event)
        
    def on_event(self, event: Event):
        # 关键修正：记录引擎当前的 timestamp (即事件到达/处理的时间)
        # 同时保存事件本身的 timestamp (即产生时间) 用于对比
        self.records.append((self.engine.timestamp, event, event.timestamp))
        
    def clear(self):
        self.records.clear()

# --- 测试用例 ---

class TestBacktestEngine:
    
    @pytest.fixture
    def setup_engine(self):
        """Fixture: 初始化 Engine 和相关组件"""
        # 1. 构造数据
        data_events = [
            Event(timestamp=0),
            Event(timestamp=2500),
            Event(timestamp=5000)
        ]
        dataset = ListDataset(data_events)
        
        # 2. 构造 DelayBus (延迟 10ms)
        s2c_bus = DelayBus(FixedDelayModel(10)) 
        c2s_bus = DelayBus(FixedDelayModel(10))
        
        # 3. 初始化引擎 (Timer 间隔 1000ms)
        engine = BacktestEngine(
            dataset=dataset,
            server2client_delaybus=s2c_bus,
            client2server_delaybus=c2s_bus,
            timer_interval=1000
        )
        
        # 4. 挂载收集器
        client_collector = EventCollector()
        server_collector = EventCollector()
        
        engine.add_component(client_collector, is_server=False)
        engine.add_component(server_collector, is_server=True)
        
        return engine, client_collector, server_collector, data_events

    def test_wiring_and_flow(self, setup_engine):
        """测试 1: 验证 DelayBus 接线和数据流向 (Server -> Client)"""
        engine, client_collector, server_collector, _ = setup_engine
        
        # 运行回测
        engine.run()
        
        # 验证 Server 端收到了原始数据 (使用 Arrival Time)
        server_arrivals = [t for t, e, _ in server_collector.records if type(e) is Event]
        assert 0 in server_arrivals
        assert 2500 in server_arrivals
        assert 5000 in server_arrivals
        
        # 验证 Client 端通过 Bus 收到了数据 (延迟 10ms)
        # 修正：断言 Arrival Time (引擎时间)，而非 Event Generation Time
        client_arrivals = [t for t, e, _ in client_collector.records if type(e) is Event and not isinstance(e, Timer)]
        
        assert 10 in client_arrivals      # 0 + 10
        assert 2510 in client_arrivals    # 2500 + 10
        assert 5010 in client_arrivals    # 5000 + 10
        
        # 验证接线
        assert engine.server2client_bus.target_engine == engine.client_engine
        assert engine.client2server_bus.target_engine == engine.server_engine

    def test_timer_generation(self, setup_engine):
        """测试 2: 验证 Timer 是否按间隔正确生成"""
        engine, client_collector, _, _ = setup_engine
        
        # 运行回测
        engine.run()
        
        # 提取 Client 端收到的 Timer 事件的到达时间
        timer_arrivals = [t for t, e, _ in client_collector.records if isinstance(e, Timer)]
        
        # 预期 Timer 到达时间: 0, 1000, 2000, 3000, 4000, 5000
        expected_arrivals = [0, 1000, 2000, 3000, 4000, 5000]
        
        assert timer_arrivals == expected_arrivals

    def test_priority_logic(self):
        """测试 3: 验证事件处理优先级 (Bus > Timer > Data)"""
        # 构造场景：T=100 时，Bus Event 和 Timer 同时发生
        data_events = [Event(0), Event(100)]
        
        # 延迟 100ms
        s2c_bus = DelayBus(FixedDelayModel(100))
        c2s_bus = DelayBus(FixedDelayModel(100))
        
        engine = BacktestEngine(
            dataset=ListDataset(data_events),
            server2client_delaybus=s2c_bus,
            client2server_delaybus=c2s_bus,
            timer_interval=100
        )
        
        client_collector = EventCollector()
        engine.add_component(client_collector, is_server=False)
        
        engine.run()
        
        # 分析 Client 在 T=100 时刻收到的事件
        # 使用 Arrival Time (t) 进行过滤
        events_at_100 = [
            (t, e) for t, e, _ in client_collector.records
            if t == 100
        ]
        
        # 预期在 T=100 时刻收到 2 个事件：
        # 1. Bus Event (来自 Data(0) + 100ms 延迟)
        # 2. Timer Event (Timer(100))
        # (Data(100) 会在 Server 处理，然后 Delay 到 T=200 才到 Client，所以此处不应出现)
        
        assert len(events_at_100) == 2
        
        first_arrival, first_event = events_at_100[0]
        second_arrival, second_event = events_at_100[1]
        
        # 验证顺序：Bus 优先于 Timer
        # 1. 第一个是普通 Event (Bus)
        assert type(first_event) is Event 
        assert not isinstance(first_event, Timer)
        
        # 2. 第二个是 Timer
        assert isinstance(second_event, Timer)
        
        print("Priority Check Passed: Bus Event processed before Timer Event at same timestamp.")

if __name__ == "__main__":
    pytest.main(["-v", __file__])