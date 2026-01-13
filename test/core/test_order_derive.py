import pytest
from hft_backtest.order import Order, ORDER_TYPE_LIMIT
from hft_backtest.event import Event

def test_order_derive_integrity():
    """
    测试 Order.derive() 是否发生了对象切片 (Object Slicing)
    """
    # 1. 创建一个完整的 Order 对象
    original_order = Order(
        1001,               # order_id
        ORDER_TYPE_LIMIT,   # order_type
        "BTC-USDT",         # symbol
        1.5,                # quantity
        50000.0             # price
    )
    assert original_order.is_limit_order
    assert not original_order.is_post_only
    # 设置父类字段
    original_order.timestamp = 123456789
    original_order.source = 1

    # 设置 Order 特有状态
    original_order.traded = 0.5
    original_order.state = 1

    # 2. 执行克隆
    cloned_order = original_order.derive()

    # --- 验证环节 ---

    # 检查点 1: 类型检查 (最关键的一步)
    print(f"Original Type: {type(original_order)}")
    print(f"Cloned Type:   {type(cloned_order)}")
    
    assert isinstance(cloned_order, Order), \
        f"严重错误：对象切片发生！期望 Order 类型，但得到了 {type(cloned_order)}。"

    # 检查点 2: 验证 derive 的语义 (重置元数据)
    # 你是对的，derive 应该重置 timestamp/source/producer
    assert cloned_order.timestamp == 0
    assert cloned_order.source == 0
    
    # 检查点 3: 子类字段完整性 (这才是证明没有发生切片的铁证)
    # 如果发生切片，这些数据会丢失
    assert cloned_order.order_id == 1001
    assert cloned_order.symbol == "BTC-USDT"
    assert cloned_order.price == 50000.0
    assert cloned_order.quantity == 1.5
    
    # 检查点 4: 状态字段
    # 根据具体的 derive 实现，这些应该被复制
    assert cloned_order.traded == 0.5
    assert cloned_order.state == 1

    # 检查点 6: post_only 字段应被保留
    assert cloned_order.is_post_only == original_order.is_post_only
    
    # 检查点 5: 模拟 DelayBus 的行为 (手动还原元数据)
    cloned_order.timestamp = original_order.timestamp
    cloned_order.source = original_order.source
    
    assert cloned_order.timestamp == 123456789
    
    print("测试通过：Order.derive() 成功复制了 Order 数据，且类型正确。")

if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])