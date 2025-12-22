import pytest
from unittest.mock import MagicMock
from loguru import logger
from hft_backtest.helper import EventPrinter, OrderTracer
from hft_backtest import Order

class DummyEvent:
    def __init__(self, ts):
        self.timestamp = ts
    def __str__(self):
        return "DummyEvent"

def test_event_printer_filtering(capsys):
    """测试 EventPrinter 的类型过滤功能"""
    # EventPrinter 使用 print()，所以用 capsys 捕获 stdout 是对的
    printer = EventPrinter(tips="[TEST]", event_types=[DummyEvent])
    
    engine = MagicMock()
    engine.timestamp = 1000
    printer.event_engine = engine
    
    e1 = DummyEvent(1000)
    printer.on_event(e1)
    
    e2 = Order.create_market("A", 1)
    printer.on_event(e2)
    
    captured = capsys.readouterr()
    assert "DummyEvent" in captured.out
    assert "Order" not in captured.out
    assert "[TEST]" in captured.out

def test_event_printer_all_events(capsys):
    printer = EventPrinter(tips="[ALL]")
    printer.event_types = {DummyEvent}
    
    engine = MagicMock()
    engine.timestamp = 2000
    printer.event_engine = engine
    
    e = DummyEvent(2000)
    printer.on_event(e)
    
    captured = capsys.readouterr()
    assert "[ALL] 2000 DummyEvent" in captured.out.strip()

def test_order_tracer_filtering():
    """测试 OrderTracer 是否只追踪特定 ID 的订单"""
    # 【修复】使用 loguru 的自定义 sink 捕获日志
    log_messages = []
    handler_id = logger.add(lambda msg: log_messages.append(msg))
    
    try:
        target_id = 999
        tracer = OrderTracer(target_order_id=target_id)
        
        engine = MagicMock()
        engine.timestamp = 5000
        tracer.event_engine = engine
        
        o1 = Order.create_limit("A", 1, 1)
        o1.order_id = target_id
        
        o2 = Order.create_limit("B", 1, 1)
        o2.order_id = 888
        
        tracer.on_order(o1)
        tracer.on_order(o2)
        
        # 验证日志内容
        # loguru 的 msg 是包含换行符的字符串
        assert any(f"OrderTracer: 5000" in m and str(target_id) in m for m in log_messages)
        assert not any(str(o2.order_id) in m for m in log_messages if "OrderTracer" in m)
        
    finally:
        logger.remove(handler_id)

def test_helper_registration():
    engine = MagicMock()
    printer = EventPrinter(event_types=[])
    printer.start(engine)
    engine.global_register.assert_called_once()
    
    tracer = OrderTracer(1)
    tracer.start(engine)
    engine.register.assert_called_with(Order, tracer.on_order)