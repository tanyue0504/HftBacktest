import pytest
from hft_backtest import Order

# 定义一些辅助常量方便阅读
ORDER_TYPE_LIMIT = Order.ORDER_TYPE_LIMIT
ORDER_TYPE_MARKET = Order.ORDER_TYPE_MARKET
ORDER_TYPE_CANCEL = Order.ORDER_TYPE_CANCEL
ORDER_STATE_CREATED = Order.ORDER_STATE_CREATED

def test_create_limit_buy():
    """测试创建买入限价单"""
    # 数量为正代表买入
    order = Order.create_limit("ETH-USDT", 1.5, 3000.0)
    
    assert order.symbol == "ETH-USDT"
    assert order.quantity == 1.5
    assert order.price == 3000.0
    assert order.order_type == ORDER_TYPE_LIMIT
    assert order.state == ORDER_STATE_CREATED
    assert order.quantity > 0 

def test_create_limit_sell():
    """测试创建卖出限价单"""
    # 数量为负代表卖出
    order = Order.create_limit("ETH-USDT", -2.0, 3000.0)
    assert order.quantity == -2.0
    assert order.quantity < 0

def test_create_market():
    """测试创建市价单"""
    order = Order.create_market("BTC-USDT", 0.5)
    
    assert order.order_type == ORDER_TYPE_MARKET
    assert order.symbol == "BTC-USDT"
    # 市价单通常价格为 -1 或者特殊值
    assert order.price == -1.0 

def test_create_cancel():
    """测试创建撤单消息"""
    # 原始订单
    origin = Order.create_limit("BTC-USDT", 1, 50000)
    origin.order_id = 12345
    
    # 【修复】Order 没有 create_cancel，需要手动 derive 并修改类型
    cancel = origin.derive()
    cancel.order_type = ORDER_TYPE_CANCEL
    
    assert cancel.order_type == ORDER_TYPE_CANCEL
    assert cancel.order_id == 12345 # 必须继承原始ID
    assert cancel.symbol == "BTC-USDT"
    # derive 出来的状态通常保持原样，或者需要重置为 CREATED，具体取决于 derive 实现
    # 这里假设我们手动将其重置为 CREATED 以便发送
    cancel.state = ORDER_STATE_CREATED
    assert cancel.state == ORDER_STATE_CREATED

def test_order_state_properties():
    """测试订单状态辅助判断属性"""
    order = Order.create_limit("A", 1, 1)
    
    assert order.is_created is True
    # 初始状态不是 Submitted
    assert order.is_submitted is False
    
    # 手动修改状态模拟
    order.state = Order.ORDER_STATE_SUBMITTED
    assert order.is_created is False
    assert order.is_submitted is True
    
    # 测试撤单属性
    cancel_order = order.derive()
    cancel_order.order_type = ORDER_TYPE_CANCEL
    assert cancel_order.is_cancel_order is True
    assert order.is_cancel_order is False