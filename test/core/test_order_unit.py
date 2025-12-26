import pytest
import sys
from hft_backtest.order import (
    Order, 
    ORDER_TYPE_LIMIT, 
    ORDER_TYPE_MARKET, 
    ORDER_TYPE_CANCEL,
    ORDER_STATE_FILLED
)

class TestOrder:
    def test_creation_and_fields(self):
        """测试基本的工厂创建和字段赋值"""
        symbol = "BTC-USDT"
        qty = 1.5
        price = 25000.0
        
        # 使用工厂创建
        o = Order.create_limit(symbol, qty, price)
        
        assert o.symbol == symbol
        assert o.quantity == qty
        assert o.price == price
        assert o.order_type == ORDER_TYPE_LIMIT
        assert o.state == 0  # ORDER_STATE_CREATED
        assert o.is_limit_order
        assert not o.is_market_order
        
        # 检查 ID 是否自动生成 (假设这是第一个或者是递增的)
        assert o.order_id > 0

    def test_cache_mechanism(self):
        """测试价格/数量的整数缓存与失效机制"""
        o = Order.create_limit("ETH", 1.0, 100.0)
        
        # 1. 初始 float -> int
        expected_int = 100 * 100000000
        assert o.price_int == expected_int
        
        # 2. 修改 float 价格
        new_price = 200.0
        o.price = new_price
        
        # int 应该自动更新
        expected_int_2 = 200 * 100000000
        assert o.price_int == expected_int_2
        
        # 3. 边界测试 (四舍五入)
        # 修改为 1.0000000151，确保二进制表示大于 1.000000015
        # 这样 * 1e8 得到 100000001.51... + 0.5 = 100000002.01... ->截断-> 100000002
        o.price = 1.0000000151
        assert o.price_int == 100000002
        
        # 测试舍去的情况
        o.price = 1.0000000149
        assert o.price_int == 100000001

    def test_derive_order(self):
        """
        测试从 Order 派生 (derive)
        关键点：检查 symbol 引用是否安全，数值是否拷贝
        """
        o1 = Order.create_limit("SOL", 10.0, 50.0)
        o1.state = ORDER_STATE_FILLED
        o1.filled_price = 50.0
        
        # 触发一下缓存生成
        _ = o1.price_int
        
        # 派生
        o2 = o1.derive()
        
        # 1. 检查基础字段拷贝
        assert o2.symbol == "SOL"
        assert o2.price == 50.0
        assert o2.quantity == 10.0
        assert o2.order_type == ORDER_TYPE_LIMIT
        assert o2.order_id == o1.order_id  # derive 只是内存拷贝，不改变 ID
        
        # 2. 检查 Event 头部被重置 (Event.derive 的行为)
        assert o2.timestamp == 0
        
        # 3. 检查 Order 状态字段 (derive 仅仅是 memcpy，所以状态也会拷过去)
        # 注意：derive() 仅仅是复制内存。
        # 如果逻辑上需要重置状态，需要在 derive 后手动设置，或者 Order 类重写 derive
        # 但目前的 Order.derive 继承自 Event，所以它会保留 state
        assert o2.state == ORDER_STATE_FILLED 
        
        # 4. 检查缓存一致性
        # o1 已经生成了缓存，memcpy 应该把 _price_int_cache 也拷过去了
        # 并且 _price_cache_valid 也是 True
        assert o2.price_int == 50 * 100000000

        # 5. 独立性测试
        o2.price = 60.0
        assert o1.price == 50.0  # 原对象不变
        assert o2.price_int == 60 * 100000000  # 新对象更新
        assert o1.price_int == 50 * 100000000  # 原对象缓存不变

    def test_create_cancel(self):
        """模拟创建撤单指令"""
        origin = Order.create_limit("BTC", 1, 10000)
        origin.order_id = 999
        
        # 撤单指令通常是把原订单 clone 一份，修改类型
        cancel_cmd = origin.derive()
        cancel_cmd.order_type = ORDER_TYPE_CANCEL
        
        assert cancel_cmd.order_id == 999
        assert cancel_cmd.is_cancel_order
        assert cancel_cmd.symbol == "BTC"
        assert not origin.is_cancel_order

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))