import pytest
from hft_backtest import Event, EventEngine
from hft_backtest.delaybus import DelayBus, FixedDelayModel

def test_delay_bus_logic():
    source = EventEngine()
    target = EventEngine()
    
    # 1. 设置 100ns 固定延迟
    model = FixedDelayModel(delay=100)
    bus = DelayBus(target, model)
    bus.start(source)
    
    received_events = []
    target.register(Event, lambda e: received_events.append(e))
    
    # 2. 发送事件 (TS=10)
    e1 = Event(timestamp=10)
    # 模拟 Source 发出事件（通常 EventEngine.put 会自动设置 source，
    # 但测试中手动设置以匹配 DelayBus 的过滤逻辑）
    e1.source = source._id 
    source.put(e1)
    
    # 3. 检查 DelayBus 状态
    # e1 应该在 10+100=110 时触发
    assert bus.next_timestamp == 110
    
    # 4. 推进时间到 100 (未到触发时间)
    bus.process_until(100)
    assert len(received_events) == 0
    
    # 5. 推进时间到 110 (正好触发)
    bus.process_until(110)
    assert len(received_events) == 1
    assert received_events[0] == e1
    
    # 验证目标引擎时间是否被同步（防止时间倒流）
    assert target.timestamp == 110

if __name__ == "__main__":
    test_delay_bus_logic()
    print("DelayBus Test Passed!")