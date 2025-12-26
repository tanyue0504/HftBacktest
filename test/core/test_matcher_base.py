import pytest
import sys
from hft_backtest.matcher import MatchEngine
from hft_backtest.event_engine import EventEngine
from hft_backtest.order import Order
from hft_backtest.event import Event

class TestMatcherBase:
    def test_abstract_enforcement(self):
        """测试基类强制要求实现 start"""
        engine = EventEngine()
        matcher = MatchEngine()
        
        # 1. start 应该报错
        with pytest.raises(NotImplementedError, match="MatchEngine.start must be implemented"):
            matcher.start(engine)
            
        # 2. stop 默认什么都不做
        matcher.stop()
        
        # 3. on_order 默认什么都不做
        o = Order.create_limit("BTC", 1, 100)
        matcher.on_order(o) 

    def test_concrete_implementation(self):
        """测试具体子类的实现流程"""
        
        class MockMatcher(MatchEngine):
            def __init__(self):
                self.orders = []
                
            def start(self, engine):
                # 注册监听
                engine.register(Order, self.on_order)
                
            def on_order(self, order):
                # 覆盖基类逻辑
                self.orders.append(order)
                
        matcher = MockMatcher()
        engine = EventEngine()
        
        # 启动
        matcher.start(engine)
        
        # 发送订单
        o = Order.create_limit("ETH", 1.5, 2000)
        engine.put(o)
        
        assert len(matcher.orders) == 1
        assert matcher.orders[0] is o

    def test_type_safety(self):
        """测试 Cython 的类型检查 (cpdef Order order)"""
        matcher = MatchEngine()
        
        # 1. 传入 Order -> OK
        o = Order.create_limit("A", 1, 1)
        matcher.on_order(o)
        
        # 2. 传入普通 Event -> TypeError
        # 因为 pxd 中声明了 cpdef on_order(self, Order order)
        e = Event(100)
        with pytest.raises(TypeError):
            matcher.on_order(e)

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))