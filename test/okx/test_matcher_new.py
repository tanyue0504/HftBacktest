import sys
import pytest
from collections import deque
from hft_backtest import EventEngine, Order
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXDelivery
# 确保你的 Matcher 类定义在正确位置，或者直接粘贴在测试文件中
from hft_backtest.okx.matcher_new import OKXMatcherNew 

class MockEventEngine(EventEngine):
    def __init__(self):
        self.queue = deque()
        self.strategies = []
    
    def put(self, event):
        self.queue.append(event)
    
    # 【修正】增加 ignore_self 参数以匹配基类签名
    def register(self, event_type, handler, ignore_self=False):
        pass
    
    def global_register(self, handler, ignore_self=False, is_senior=False):
        pass

class TestOKXMatcher:
    def setup_method(self):
        self.engine = MockEventEngine()
        self.symbol = "BTC-USDT"
        self.matcher = OKXMatcherNew(self.symbol)
        self.matcher.start(self.engine)
        
        # 初始化默认盘口
        self.matcher.best_bid_price_int = 100 * self.matcher.PRICE_SCALAR
        self.matcher.best_ask_price_int = 101 * self.matcher.PRICE_SCALAR

    # --- Helper Methods ---

    def create_ticker(self, bid, ask, bid_qty=1.0, ask_qty=1.0):
        # 修正：OKXBookticker 没有 best_bid_price，应该用 bid_price_1
        # Cython 类初始化通常需要指定参数，或者创建后赋值
        ticker = OKXBookticker(symbol=self.symbol)
        
        # 填充 Depth 1 (Best Bid/Ask)
        ticker.bid_price_1 = bid
        ticker.bid_amount_1 = bid_qty
        ticker.ask_price_1 = ask
        ticker.ask_amount_1 = ask_qty
        
        # 填充 Depth 2-5 防止 attrgetter 报错
        for i in range(2, 6):
            setattr(ticker, f"bid_price_{i}", bid - i * 0.1)
            setattr(ticker, f"bid_amount_{i}", 1.0)
            setattr(ticker, f"ask_price_{i}", ask + i * 0.1)
            setattr(ticker, f"ask_amount_{i}", 1.0)
            
        return ticker

    def create_trade(self, price, size, side):
        # 修正：OKXTrades 初始化
        return OKXTrades(
            symbol=self.symbol,
            price=price,
            size=size,
            side=side
        )

    def create_limit_order(self, price, qty, oid):
        # 修正：Order 必须通过构造函数传参，不能无参初始化
        # 假设 oid 是 int 或可转 int
        order_id = int(oid)
        
        order = Order(
            order_id,                   # order_id
            Order.ORDER_TYPE_LIMIT,     # order_type
            self.symbol,                # symbol
            float(qty),                 # quantity
            float(price)                # price
        )
        
        # 状态需要单独设置，默认是 CREATED
        order.state = Order.ORDER_STATE_SUBMITTED
        return order

    # --- Test Cases ---

    def test_01_limit_maker_entry(self):
        """测试限价单挂单入书"""
        order = self.create_limit_order(99, 1.0, "1")
        self.matcher.on_order(order)
        
        # 验证收到 RECEIVED 事件
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_RECEIVED
        
        # 验证在 Buy Book 中
        # 注意：这里假设 buy_book 存的是 Order 对象引用
        assert len(self.matcher.buy_book) == 1
        assert self.matcher.buy_book[0].order_id == 1

    def test_02_limit_taker_fill(self):
        """测试限价单吃单立即成交"""
        order = self.create_limit_order(102, 1.0, "2")
        self.matcher.on_order(order)
        
        # 期望 RECEIVED -> FILLED
        assert len(self.engine.queue) == 2
        
        evt_recv = self.engine.queue.popleft()
        assert evt_recv.state == Order.ORDER_STATE_RECEIVED
        
        evt_fill = self.engine.queue.popleft()
        assert evt_fill.state == Order.ORDER_STATE_FILLED
        assert evt_fill.filled_price == 101.0  # 对手价成交
        
        assert len(self.matcher.buy_book) == 0

    def test_03_trade_sweeping_passive(self):
        """测试 Trade 事件扫掉被动单"""
        # 1. Maker Order
        order = self.create_limit_order(100, 1.0, "3")
        self.matcher.on_order(order)
        self.engine.queue.clear()
        
        # 2. Trade Event (Seller Taker 砸到 99)
        trade = self.create_trade(99, 5.0, 'sell')
        self.matcher.on_trade(trade)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_FILLED
        assert evt.order_id == 3

    def test_04_trade_logic_your_special_case(self):
        """验证 Trade 更新 BBO 后触发 Maker 成交"""
        self.matcher.best_bid_price_int = 90 * self.matcher.PRICE_SCALAR
        self.matcher.best_ask_price_int = 100 * self.matcher.PRICE_SCALAR
        
        # 1. 挂买单 95 ( < Ask 100)
        order = self.create_limit_order(95, 1.0, "4")
        self.matcher.on_order(order)
        self.engine.queue.clear()
        
        # 2. Trade: Buyer Taker 成交在 92 (说明 Ask 掉到了 92)
        trade = self.create_trade(92, 0.5, 'buy')
        self.matcher.on_trade(trade)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_FILLED
        assert evt.filled_price == 92.0

    def test_05_rank_queue_logic(self):
        """测试排队逻辑"""
        # 1. 初始化盘口
        ticker = self.create_ticker(100, 101, bid_qty=1000, ask_qty=1000)
        self.matcher.on_bookticker(ticker)
        
        # 2. 下单
        order = self.create_limit_order(100, 10, "5")
        self.matcher.on_order(order)
        self.engine.queue.clear()
        
        # Rank 初始化 (等待下一个 ticker)
        self.matcher.on_bookticker(ticker)
        
        # 3. Trade 1: 消耗 500 (剩余前面还有 500)
        trade1 = self.create_trade(100, 500, 'sell')
        self.matcher.on_trade(trade1)
        assert len(self.engine.queue) == 0
        
        # 4. Trade 2: 消耗 600 (总消耗 1100 > 前面 1000 + 自己 10)
        trade2 = self.create_trade(100, 600, 'sell')
        self.matcher.on_trade(trade2)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_FILLED

if __name__ == '__main__':
    sys.exit(pytest.main(["-v", __file__]))