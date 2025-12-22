import pytest
from unittest.mock import MagicMock
from hft_backtest import Strategy, Order, Account, EventEngine
from hft_backtest.order import Order, ORDER_TYPE_LIMIT, ORDER_STATE_CREATED, ORDER_STATE_SUBMITTED, ORDER_TYPE_CANCEL

# Mock 对象
class MockAccount(Account):
    def __init__(self):
        pass

class MockEventEngine:
    def __init__(self):
        self.events = []
    
    def put(self, event):
        self.events.append(event)

class ConcreteStrategy(Strategy):
    """用于测试的具体策略实现"""
    def __init__(self, account):
        super().__init__(account)
    
    def on_event(self, event):
        pass

@pytest.fixture
def strategy_env():
    account = MockAccount()
    strategy = ConcreteStrategy(account)
    engine = MockEventEngine()
    strategy.event_engine = engine # 模拟注入 Engine
    return strategy, engine

def test_strategy_init():
    """测试策略初始化及组件属性"""
    account = MockAccount()
    strategy = ConcreteStrategy(account)
    assert strategy.account == account
    assert isinstance(strategy, Strategy)

def test_send_limit_order(strategy_env):
    """测试发送限价单流程"""
    strategy, engine = strategy_env
    
    # 1. 创建订单
    order = Order.create_limit("BTC-USDT", 1, 50000)
    assert order.state == ORDER_STATE_CREATED
    
    # 2. 发送订单
    strategy.send_order(order)
    
    # 3. 验证状态变更和引擎接收
    assert order.state == ORDER_STATE_SUBMITTED
    assert len(engine.events) == 1
    assert engine.events[0] == order
    assert engine.events[0].order_id == order.order_id

def test_send_market_order(strategy_env):
    """测试发送市价单流程"""
    strategy, engine = strategy_env
    order = Order.create_market("BTC-USDT", 1)
    
    strategy.send_order(order)
    
    assert order.state == ORDER_STATE_SUBMITTED
    assert engine.events[0].order_type != ORDER_TYPE_LIMIT

def test_send_cancel_order(strategy_env):
    """测试发送撤单请求"""
    strategy, engine = strategy_env
    
    # 先造一个原始订单
    orig_order = Order.create_limit("BTC-USDT", 1, 50000)
    orig_order.order_id = 888
    
    # 【修复点】使用 derive 创建撤单
    cancel_req = orig_order.derive()
    cancel_req.order_type = ORDER_TYPE_CANCEL
    
    strategy.send_order(cancel_req)
    
    assert cancel_req.state == ORDER_STATE_SUBMITTED
    assert len(engine.events) == 1
    # 验证撤单请求指向了正确的原始ID
    assert engine.events[0].order_id == 888 

def test_send_order_assertion_error(strategy_env):
    """测试重复发送订单应抛出断言错误"""
    strategy, engine = strategy_env
    order = Order.create_limit("BTC-USDT", 1, 50000)
    
    # 第一次发送成功
    strategy.send_order(order)
    assert order.state == ORDER_STATE_SUBMITTED
    
    # 第二次发送同一订单，状态已非CREATED，应报错
    with pytest.raises(AssertionError):
        strategy.send_order(order)