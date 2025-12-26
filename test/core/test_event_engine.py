import pytest
import sys
from hft_backtest.event import Event
from hft_backtest.event_engine import EventEngine

# 定义一些测试用的子类
class MarketEvent(Event):
    pass

class OrderEvent(Event):
    pass

class TestEventEngine:
    def test_clock_update(self):
        """测试逻辑时钟更新机制"""
        engine = EventEngine()
        assert engine.timestamp == 0
        
        # 1. 推送带时间的事件 -> 更新引擎时间
        e1 = Event(100)
        engine.put(e1)
        assert engine.timestamp == 100
        assert e1.timestamp == 100
        
        # 2. 推送时间较早的事件 -> 引擎时间不回退
        e2 = Event(90)
        engine.put(e2)
        assert engine.timestamp == 100  # 保持 100
        assert e2.timestamp == 90       # 事件时间保持原样
        
        # 3. 推送无时间事件 -> 继承引擎时间
        e3 = Event(0)
        engine.put(e3)
        assert engine.timestamp == 100
        assert e3.timestamp == 100      # 被赋值为 100

    def test_dispatch_order(self):
        """测试分发顺序：Senior -> Specific -> Junior"""
        engine = EventEngine()
        result = []
        
        def handler_senior(e): result.append("senior")
        def handler_spec(e): result.append("spec")
        def handler_junior(e): result.append("junior")
        
        engine.global_register(handler_senior, is_senior=True)
        engine.global_register(handler_junior, is_senior=False)
        engine.register(Event, handler_spec)
        
        engine.put(Event(1))
        
        assert result == ["senior", "spec", "junior"]

    def test_no_polymorphic_dispatch(self):
        """验证：不支持多态分发 (父类监听器收不到子类事件)"""
        engine = EventEngine()
        received = []
        
        def handler(e): received.append(e)
        
        # 注册监听 Event
        engine.register(Event, handler)
        
        # 发送 MarketEvent (继承自 Event)
        engine.put(MarketEvent(1))
        
        # 预期：收不到
        assert len(received) == 0
        
        # 发送 Event
        engine.put(Event(1))
        assert len(received) == 1

    def test_ignore_self_behavior(self):
        """
        深度测试 ignore_self 的行为边界
        """
        engine = EventEngine()
        results = []

        class Strategy:
            def on_trigger(self, event):
                # 这个方法产生事件
                new_event = Event(0)
                # 这里的 producer 会被标记为 on_trigger 的 ID
                engine.put(new_event)
            
            def on_echo_default(self, event):
                # 默认 ignore_self=True
                results.append("echo_default")
                
            def on_echo_force(self, event):
                # 强制 ignore_self=False
                results.append("echo_receive")

        s = Strategy()
        
        # 1. 注册 on_trigger 监听 MarketEvent
        engine.register(MarketEvent, s.on_trigger)
        
        # 2. 注册 echo 监听 Event (on_trigger 发出的就是 Event)
        # 注意：这里我们测试的是“不同方法”之间的隔离性
        engine.register(Event, s.on_echo_default, ignore_self=True)
        engine.register(Event, s.on_echo_force, ignore_self=False)
        
        # 3. 触发
        engine.put(MarketEvent(1))
        
        # 分析：
        # MarketEvent -> on_trigger -> put(Event)
        # Event.producer == id(on_trigger)
        # 
        # 分发 Event:
        # Check on_echo_default: ignore_self=True. 
        #     Condition: producer(id_trigger) == listener(id_echo_default)?
        #     NO. They are different methods.
        #     Result: on_echo_default Should run.
        
        assert "echo_default" in results
        assert "echo_receive" in results
        
        # 结论：ignore_self 只能防止递归调用同一个 handler，不能隔离组件内的不同 handler

    def test_ignore_self_recursion(self):
        """测试 ignore_self 确实能防止自递归"""
        engine = EventEngine()
        count = [0]
        
        def recursive_handler(event):
            count[0] += 1
            if count[0] < 5:
                # 发出一个同样类型的事件
                engine.put(Event(0))
        
        # 注册并开启 ignore_self (默认)
        engine.register(Event, recursive_handler, ignore_self=True)
        
        engine.put(Event(1))
        
        # 如果 ignore_self 工作，recursive_handler 发出的事件会被它自己忽略
        # 所以 count 应该是 1
        assert count[0] == 1

    def test_exception_crash(self):
        """测试异常会中断引擎"""
        engine = EventEngine()
        
        def bad_handler(e):
            raise ValueError("Boom")
            
        def good_handler(e):
            # 这个不应该被执行，因为前面炸了
            e.timestamp = 9999
            
        engine.register(Event, bad_handler)
        engine.register(Event, good_handler) # 注意：list顺序，append在后
        
        e = Event(1)
        with pytest.raises(ValueError, match="Boom"):
            engine.put(e)
            
        # 验证 good_handler 没有运行
        assert e.timestamp == 1

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))