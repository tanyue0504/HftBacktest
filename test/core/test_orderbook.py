# pytest test/core/test_orderbook.py -v

import pytest
from hft_backtest.orderbook import PyOrderBook

# 常量定义
HUGE_RANK = 1e15
BUY = True
SELL = False

@pytest.fixture
def ob():
    return PyOrderBook()

class TestOrderBookBasic:
    """基础功能测试：增删改查"""
    
    def test_lifecycle(self, ob):
        """测试下单、查询、撤单的完整生命周期"""
        # 1. 下单
        ob.add_order(1, BUY, 100.0, 10.0, 0)
        assert ob.has_order(1) is True
        
        # 2. 重复下单应当被忽略
        ob.add_order(1, BUY, 100.0, 20.0, 0)
        # 无法直接查数量，但可以通过后续 reduce/cancel 验证，或者相信 C++ 逻辑
        
        # 3. 撤单
        ob.cancel_order(1)
        assert ob.has_order(1) is False
        
        # 4. 撤销不存在的单子不应报错
        ob.cancel_order(999)

    def test_reduce_qty(self, ob):
        """测试减量逻辑，以及减为0自动撤单"""
        # 下单 10 个
        ob.add_order(1, BUY, 100.0, 10.0, 500.0)
        
        # 减去 4 个
        ob.reduce_qty(1, 4.0)
        assert ob.has_order(1) is True
        
        # 再减去 6 个 (变为0)
        ob.reduce_qty(1, 6.0)
        assert ob.has_order(1) is False  # 应自动撤单


class TestOrderBookExecution:
    """核心撮合逻辑测试：Touch (排队) 和 Sweep (穿价)"""

    def test_touch_fill_logic(self, ob):
        """
        测试同价位排队成交逻辑 (Touch)
        场景：
        1. 挂买单 @ 100, Rank=500 (前面有500个)
        2. Trade @ 100, Vol=200 -> Rank变300, 不成交
        3. Trade @ 100, Vol=400 -> Rank变-100, 成交
        """
        ob.add_order(1, BUY, 100.0, 10.0, 500.0)
        
        # 第一笔 Trade，只消耗 Rank
        ob.execute_trade(True, 100.0, 200.0)
        fills = ob.get_fills()
        assert len(fills) == 0
        
        # 第二笔 Trade，消耗剩余 Rank 并成交
        # 前面剩 300，这笔 400，足以吃到我
        ob.execute_trade(True, 100.0, 400.0)
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].order_id == 1
        assert fills[0].qty == 10.0
        assert fills[0].price == 100.0

    def test_sweep_fill_logic(self, ob):
        """
        测试穿价成交逻辑 (Sweep)
        场景：
        1. 挂买单 @ 100, Rank=500 (Rank很大也没用，因为价格优)
        2. Trade @ 99 (卖方直接砸穿100)
        3. 应立即完全成交
        """
        ob.add_order(1, BUY, 100.0, 10.0, 500.0)
        
        # 价格穿透，无视 Rank
        ob.execute_trade(True, 99.0, 100.0) # 哪怕 Trade 量只有 100，只要价格穿了，我作为更优价必须成交
        
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].order_id == 1
        assert fills[0].price == 100.0 # 注意：通常回测里 Maker 拿到的还是自己的挂单价

    def test_multi_level_sweep(self, ob):
        """
        测试多档位穿价顺序
        场景：买一 100，买二 99。Trade 砸到 98。应该先成交 100，再成交 99。
        """
        ob.add_order(1, BUY, 100.0, 1.0, 0)
        ob.add_order(2, BUY, 99.0, 1.0, 0)
        
        ob.execute_trade(True, 98.0, 1000.0)
        
        fills = ob.get_fills()
        assert len(fills) == 2
        # 验证顺序：价格优先
        assert fills[0].order_id == 1  # 100 先成交
        assert fills[1].order_id == 2  # 99 后成交


class TestBBOInteraction:
    """测试最复杂的 BBO 互动逻辑：惰性重置与隐式成交"""

    def test_lazy_reset_activation(self, ob):
        """
        测试深单激活 (Lazy Reset)
        这是本架构的核心设计，必须严格测试。
        场景：
        1. 挂买单 @ 100, Rank=HUGE (埋伏)
        2. Trade @ 100, Vol=1000 -> 不应成交 (因为 Rank 巨大)
        3. BBO Update: Bid=100, Qty=500 -> Rank 重置为 500
        4. Trade @ 100, Vol=600 -> 成交 (500 < 600)
        """
        # 1. 埋伏
        ob.add_order(1, BUY, 100.0, 10.0, HUGE_RANK)
        
        # 2. 盲目的 Trade (模拟还没有收到 BBO 更新时的 Trade)
        ob.execute_trade(True, 100.0, 10000.0) # 哪怕量很大
        fills = ob.get_fills()
        assert len(fills) == 0 # Rank 1e15，扣不完，不成交
        
        # 3. BBO 来了，叫醒服务
        ob.update_bbo(BUY, 100.0, 500.0)
        
        # 此时内部 Rank 应该变成了 500
        
        # 4. 新的 Trade
        ob.execute_trade(True, 100.0, 501.0) # 刚好扣完 500
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].order_id == 1

    def test_implicit_sweep_by_bbo(self, ob):
        """
        测试 BBO 跳空导致的隐式成交
        场景：
        1. 挂卖单 @ 100
        2. 突然市场暴拉，Bid 直接变成 101 (跳空高开)
        3. 卖单 @ 100 应该立即成交
        """
        ob.add_order(1, SELL, 100.0, 10.0, 0)
        
        # BBO Update: Bid=101, Qty=100
        # 此时我的卖单 100 比 市场买一 101 还便宜，必须立即成交
        ob.update_bbo(BUY, 101.0, 100.0)
        
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].order_id == 1
        assert fills[0].price == 100.0


class TestPrecisionAndEdgeCases:
    """测试精度和边缘情况"""

    def test_precision_rounding(self, ob):
        """
        测试浮点转整数的精度
        系统精度设定为 1e8。
        测试 100.000000001 是否会被当作 100.0
        """
        # 100.0
        ob.add_order(1, BUY, 100.0, 10.0, 0)
        
        # 100.0 + 1e-9 (小于 1e-8，会被舍弃)
        # 如果是 double 比较，这俩不相等。如果是 int 1e8，这俩应该相等。
        epsilon_price = 100.0 + 1e-9
        
        # 试图撤单，如果能撤掉，说明内部存储的 key 就是 100.0
        # 但我们 cancel 是 by ID 的。
        # 我们用 add_order 的同价队列特性来测。
        
        # 加一个微小差别的单子
        ob.add_order(2, BUY, epsilon_price, 10.0, 0)
        
        # 此时如果精度生效，这俩单子应该在同一个 Price Level (100.0)
        # 我们用 Trade @ 100.0 来扫，看是否都能成交
        ob.execute_trade(True, 100.0, 20.0)
        
        fills = ob.get_fills()
        assert len(fills) == 2 # 两个都成交了，说明被归并到了同一个价格档位

    def test_partial_fill(self, ob):
        """测试部分成交和剩余量"""
        ob.add_order(1, BUY, 100.0, 10.0, 0) # Rank 0
        
        # Trade 1: 只成交 4 个
        ob.execute_trade(True, 100.0, 4.0)
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].qty == 4.0
        assert ob.has_order(1) is True # 还没完
        
        # Trade 2: 再成交 6 个
        ob.execute_trade(True, 100.0, 6.0)
        fills = ob.get_fills()
        assert len(fills) == 1
        assert fills[0].qty == 6.0
        assert ob.has_order(1) is False # 完了