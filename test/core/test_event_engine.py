import pytest
from hft_backtest.event_engine import EventEngine
from hft_backtest.event import Event

# 定义用于测试的子事件
class TypeAEvent(Event):
    pass

class TypeBEvent(Event):
    pass

def test_basic_handling():
    """测试基础的注册和事件分发"""
    engine = EventEngine()
    received = []

    def on_event(event):
        received.append(event)

    engine.register(TypeAEvent, on_event)
    
    # 推送事件
    evt = TypeAEvent(100)
    engine.put(evt)

    assert len(received) == 1
    assert received[0] == evt
    assert engine.timestamp == 100

def test_execution_order():
    """测试监听器执行顺序：Senior Global -> Specific -> Junior Global"""
    engine = EventEngine()
    order = []

    def senior_listener(event):
        order.append("senior")

    def specific_listener(event):
        order.append("specific")

    def junior_listener(event):
        order.append("junior")

    # 注册不同优先级的监听器
    engine.global_register(senior_listener, is_senior=True)
    engine.register(TypeAEvent, specific_listener)
    engine.global_register(junior_listener, is_senior=False)

    engine.put(TypeAEvent(1))

    assert order == ["senior", "specific", "junior"]

def test_timestamp_logic():
    """测试时间戳更新逻辑"""
    engine = EventEngine()
    engine.timestamp = 500

    # 1. 传入 0 时间戳事件 -> 应该继承引擎时间
    evt1 = TypeAEvent(0)
    engine.put(evt1)
    assert evt1.timestamp == 500
    assert engine.timestamp == 500

    # 2. 传入更小的时间戳 -> 应该保留原时间戳，且不更新引擎时间 (历史回放或乱序数据场景)
    evt2 = TypeAEvent(400)
    engine.put(evt2)
    assert evt2.timestamp == 400
    assert engine.timestamp == 500

    # 3. 传入更大的时间戳 -> 应该更新引擎时间
    evt3 = TypeAEvent(600)
    engine.put(evt3)
    assert evt3.timestamp == 600
    assert engine.timestamp == 600

def test_ignore_self_true():
    """测试 ignore_self=True (默认): 监听器不应收到自己发出的事件"""
    engine = EventEngine()
    received_b = []

    def chain_reaction_listener(event):
        # 收到 A 后发出 B
        if isinstance(event, TypeAEvent):
            engine.put(TypeBEvent(event.timestamp + 1))
        # 收到 B 后记录
        elif isinstance(event, TypeBEvent):
            received_b.append(event)

    # 注册监听器同时监听 A 和 B
    # 对于 B 事件，ignore_self=True 是默认行为
    engine.register(TypeAEvent, chain_reaction_listener)
    engine.register(TypeBEvent, chain_reaction_listener, ignore_self=True)

    engine.put(TypeAEvent(1))

    # 结果：监听器发出了 B，但因为它被注册为忽略自己发出的 B，所以 received_b 应该为空
    assert len(received_b) == 0

def test_ignore_self_false():
    """测试 ignore_self=False: 监听器可以收到自己发出的事件"""
    engine = EventEngine()
    received_b = []

    def chain_reaction_listener(event):
        if isinstance(event, TypeAEvent):
            engine.put(TypeBEvent(event.timestamp + 1))
        elif isinstance(event, TypeBEvent):
            received_b.append(event)

    engine.register(TypeAEvent, chain_reaction_listener)
    # 显式允许接收自己产生的事件
    engine.register(TypeBEvent, chain_reaction_listener, ignore_self=False)

    engine.put(TypeAEvent(1))

    # 结果：应该收到 B
    assert len(received_b) == 1
    assert isinstance(received_b[0], TypeBEvent)

def test_source_tagging():
    """测试事件来源(Source)标注"""
    engine = EventEngine()
    
    def on_event(e):
        pass
    
    engine.register(TypeAEvent, on_event)
    
    evt = TypeAEvent(1)
    assert evt.source == 0 # 初始为 0/None
    
    engine.put(evt)
    
    # 引擎应该将 source 标记为引擎的 id
    assert evt.source == id(engine)

if __name__ == "__main__":
    # 手动运行测试
    test_basic_handling()
    test_execution_order()
    test_timestamp_logic()
    test_ignore_self_true()
    test_ignore_self_false()
    test_source_tagging()
    print("All tests passed!")