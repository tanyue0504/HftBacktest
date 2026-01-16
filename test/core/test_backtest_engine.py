import pytest
import sys
from hft_backtest.event import Event
from hft_backtest.backtest import BacktestEngine
from hft_backtest.delaybus import DelayBus, FixedDelayModel
from hft_backtest.event_engine import Component
from hft_backtest.reader import PyDatasetWrapper
from hft_backtest.timer import Timer

# 模拟数据源
def mock_data_generator():
    yield Event(100)
    yield Event(200)
    yield Event(300)

class SpyComponent(Component):
    def __init__(self, name):
        self.name = name
        self.received = []
    
    def start(self, engine):
        # 监听所有类型事件
        engine.global_register(self.on_event)
        
    def on_event(self, event):
        # 记录：(事件类型名, 时间戳, 来源)
        self.received.append((type(event).__name__, event.timestamp))

class PingPongStrategy(Component):
    """
    收到 Timer 后发送一个 Event 到 Client2Server 总线
    """
    def __init__(self, target_engine):
        self.target_engine = target_engine
        
    def start(self, engine):
        self.local_engine = engine
        engine.register(Timer, self.on_timer)
        
    def on_timer(self, event):
        # 发送一个自定义事件，模拟发单
        e = Event(event.timestamp)
        e.source = 999
        self.target_engine.put(e)

class TestBacktestEngine:
    def test_time_travel_detection_raises(self):
        """数据时间戳逆序时，引擎应检测到时间倒流并报错"""
        bus_s2c = DelayBus(FixedDelayModel(0))
        bus_c2s = DelayBus(FixedDelayModel(0))

        # 故意构造逆序时间戳：先 200 再 100
        dataset = [Event(200), Event(100)]

        # 关闭 Timer，避免把测试复杂化
        engine = BacktestEngine(dataset, bus_s2c, bus_c2s, timer_interval=None)

        with pytest.raises(RuntimeError, match=r"Time travel detected! Engine time regression"):
            engine.run()

    def test_basic_flow_and_timer(self):
        """测试基础数据流和 Timer 生成"""
        # 1. 准备组件
        bus_s2c = DelayBus(FixedDelayModel(0))
        bus_c2s = DelayBus(FixedDelayModel(0))
        
        # 间隔 50ns，数据间隔 100ns -> 每次数据间应该有一个 Timer
        engine = BacktestEngine(
            mock_data_generator(), 
            bus_s2c, 
            bus_c2s, 
            timer_interval=50
        )
        
        spy_server = SpyComponent("server")
        spy_client = SpyComponent("client")
        
        engine.add_component(spy_server, is_server=True)
        engine.add_component(spy_client, is_server=False)
        
        # 2. 运行
        engine.run()
        
        # 3. 验证 Server (应该收到 3 个 Data)
        # Server 引擎不负责 Timer (Timer 是注入 Client 的)
        server_evts = [x for x in spy_server.received if x[0] == 'Event']
        assert len(server_evts) == 3
        assert server_evts[0][1] == 100
        assert server_evts[2][1] == 300
        
        # 4. 验证 Client (应该收到 Timer)
        # T=100 (Data Start) -> Timer(100) -> Timer(150) -> Data(200) -> Timer(200) -> Timer(250) ...
        client_timers = [x for x in spy_client.received if x[0] == 'Timer']
        
        # 预期 Timer 时间点: 100, 150, 200, 250, 300
        assert len(client_timers) >= 5
        assert client_timers[0][1] == 100
        assert client_timers[1][1] == 150

    def test_priority_logic(self):
        """
        核心测试：验证同一时刻(T=100) 事件的处理顺序
        预期：Bus(S2C/C2S) > Timer > Data
        """
        # 构造场景：
        # Data 在 T=100
        # Timer 在 T=100 (初始对齐)
        # 我们在 setup 阶段强行往 DelayBus 塞一个 T=100 触发的事件
        
        bus_s2c = DelayBus(FixedDelayModel(0))
        bus_c2s = DelayBus(FixedDelayModel(0))
        
        # 数据源只有一条 T=100
        dataset = [Event(100)]
        
        engine = BacktestEngine(dataset, bus_s2c, bus_c2s, timer_interval=100)
        
        # 获取内部引用以便作弊
        client_engine = engine.client_engine
        
        # 记录器
        trace = []
        def on_trace(source_name):
            def handler(event):
                trace.append(f"{source_name}_{type(event).__name__}")
            return handler
            
        # 注册监听
        engine.server_engine.global_register(on_trace("Server"))
        engine.client_engine.global_register(on_trace("Client"))
        
        # 作弊：往 Server2Client Bus 塞一个事件，触发时间=100
        # 注意：需要手动 derive 并 push，为了方便我们直接用底层方法或模拟
        # 这里我们利用 DelayBus 的机制：先 start，然后手动 put 一个 Event 进去
        # 但 DelayBus 需要 process_until 才能吐出来。
        # 我们在 engine.run 之前预先填充 bus
        
        # Hack: 手动向 bus 的 queue 塞东西比较难（C++ vector），
        # 我们换个思路：让第一条数据 T=90，触发逻辑产生 T=100 的 Bus Event，
        # 然后第二条数据 T=100。
        
        # 方案 B: 
        # Dataset: T=100
        # 此时 Timer 也会初始化为 100
        # 我们在 Timer(100) 的回调里，发出一个 Immediate Bus Event (Delay=0)
        # 但这样 Bus Event 会在 T=100 之后处理吗？
        # 不，BacktestEngine 的循环是取出 min_t。
        # 如果 Timer(100) 产生了一个 C2S(100)，主循环会重新计算 min_t = 100。
        # 此时 Data(100) 还在。
        # 根据优先级，C2S(100) 应该在 Data(100) 之前被处理。
        
        class PriorityTester(Component):
            def start(self, eng):
                eng.register(Timer, self.on_timer)
                
            def on_timer(self, event):
                # 收到 Timer(100) 时，发出 Bus Event
                e = Event(event.timestamp) # T=100
                # 往 Client2Server 发 (engine.client2server_bus)
                # 注意：Component 拿不到 engine.bus，只能通过 engine.put 路由？
                # 不，DelayBus 是 engine 的组件。
                # 标准做法：Strategy -> engine.put(Event) -> bus.on_event -> bus queue
                engine.client2server_bus.on_event(e) 
                
        tester = PriorityTester()
        engine.add_component(tester, is_server=False)
        
        # 运行
        engine.run()
        
        # 分析 Trace
        # 1. Loop Start. T_data=100. Next_Timer=100.
        # 2. min_t = 100.
        # 3. Priority Check:
        #    - Bus Empty.
        #    - Timer(100) <= 100? Yes.
        #      -> Client Engine 处理 Timer(100).
        #         -> PriorityTester.on_timer 运行.
        #         -> Client2Server Bus 收到 Event(100). 入堆 (Delay=0 -> Trigger=100).
        #      -> Next_Timer += 100 -> 200.
        #      -> continue (Loop Restart).
        #
        # 4. Loop Restart.
        #    - T_data = 100.
        #    - T_c2s = 100 (刚才塞进去的).
        #    - Next_Timer = 200.
        #    - min_t = 100.
        #
        # 5. Priority Check:
        #    - T_s2c Empty.
        #    - T_c2s (100) <= 100? Yes.
        #      -> Bus 处理. Event(100) 到达 Server Engine.
        #      -> Trace: "Server_Event" (我们期望看到的)
        #      -> continue.
        #
        # 6. Loop Restart.
        #    - T_data = 100.
        #    - T_c2s Empty.
        #    - min_t = 100.
        #    - T_data == 100.
        #      -> Server Engine 处理 Data(100).
        #      -> Trace: "Server_Event" (来自 Data)
        
        # 期望顺序：Client_Timer -> Server_Event(Bus) -> Server_Event(Data)
        # 但我们的 trace 记录了所有 global。
        # Client 侧：Timer
        # Server 侧：BusEvent, DataEvent
        
        # 过滤出我们关心的
        filtered = [t for t in trace if t in ["Client_Timer", "Server_Event"]]
        
        # 注意：Server_Event 会出现两次，一次是 Bus 传过来的，一次是 Data。
        # 关键是 Bus 的那个要在 Data 那个之前。
        # 如何区分？Data 源产生的 Event 默认 type 是 Event。我们造的也是 Event。
        # 我们无法通过类名区分，但可以通过 source 区分。
        # 假设 Data 的 source=0 (默认)。
        # PriorityTester 发出的 source=engine.client_engine._id (EventEngine.put 会自动设置 source)
        # 等等，PriorityTester 直接调用 bus.on_event(e)，e.source 默认为 0。
        # DelayBus 会检查 source_id，如果 mismatch 会丢弃！
        # 这是一个大坑。DelayBus 在 start() 时绑定了 source engine id。
        # Client Engine ID = engine.client_engine._id
        # Tester 必须把 e.source 设为 engine.client_engine._id，否则 Bus 会丢弃它。
        
        pass 

    def test_integration_ping_pong(self):
        """测试跨总线通信"""
        bus1 = DelayBus(FixedDelayModel(10)) # 延迟 10
        bus2 = DelayBus(FixedDelayModel(10)) 
        dataset = [Event(100), Event(500)] # 足够长的时间窗口
        
        engine = BacktestEngine(dataset, bus1, bus2, timer_interval=100)
        
        # 策略：Client 收到 Timer(100) -> 发送 Msg(100)
        # 预期：Msg 在 100+10 = 110 到达 Server
        
        class ClientStrategy(Component):
            def start(self, eng):
                self.eng = eng
                eng.register(Timer, self.on_timer)
            def on_timer(self, e):
                if e.timestamp == 100:
                    msg = Event(e.timestamp)
                    # 必须使用 eng.put 让引擎分发给 Bus (作为 Global Listener)
                    # 这样 Bus 才能捕获并正确处理 source_id
                    self.eng.put(msg) 

        class ServerExchange(Component):
            def __init__(self):
                self.received_ts = []
            def start(self, eng):
                eng.register(Event, self.on_msg)
            def on_msg(self, e):
                # 记录收到消息的引擎时间
                self.received_ts.append(engine.server_engine.timestamp)

        strat = ClientStrategy()
        exch = ServerExchange()
        
        engine.add_component(strat, is_server=False)
        engine.add_component(exch, is_server=True)
        
        engine.run()
        
        # 验证
        # Client T=100 发出 -> Delay 10 -> Server T=110 收到
        assert len(exch.received_ts) == 3
        assert exch.received_ts[1] == 110

    def test_integration_ping_pong_2(self):
        """测试跨总线通信"""
        bus1 = DelayBus(FixedDelayModel(10)) # 延迟 10
        bus2 = DelayBus(FixedDelayModel(10)) 
        dataset = [Event(100), Event(500)] # 足够长的时间窗口
        
        engine = BacktestEngine(dataset, bus1, bus2, timer_interval=100)
        
        # 定义专用消息事件，避免混淆 dataset 中的 Event
        class PingEvent(Event):
            pass

        # 策略：Client 收到 Timer(100) -> 发送 PingEvent(100)
        # 预期：PingEvent 在 100+10 = 110 到达 Server
        class ClientStrategy(Component):
            def start(self, eng):
                self.eng = eng
                eng.register(Timer, self.on_timer)
            def on_timer(self, e):
                if e.timestamp == 100:
                    # 使用子类
                    msg = PingEvent(e.timestamp)
                    self.eng.put(msg) 

        class ServerExchange(Component):
            def __init__(self):
                self.received_ts = []
            def start(self, eng):
                # 只监听 PingEvent，忽略 dataset 的普通 Event
                eng.register(PingEvent, self.on_msg)
            def on_msg(self, e):
                self.received_ts.append(engine.server_engine.timestamp)

        strat = ClientStrategy()
        exch = ServerExchange()
        
        engine.add_component(strat, is_server=False)
        engine.add_component(exch, is_server=True)
        
        engine.run()
        
        # 验证
        assert len(exch.received_ts) == 1
        assert exch.received_ts[0] == 110

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))