import sys
import pytest
from collections import deque
from hft_backtest import EventEngine, Order
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXDelivery
from hft_backtest.okx.matcher import OKXMatcher

# 【关键修复】必须继承 EventEngine
class MockEventEngine(EventEngine):
    def __init__(self):
        super().__init__()
        self.queue = deque()
        self.strategies = []
        # 添加 events 列表以便像 test_matcher.py 那样断言
        self.events = []
    
    def put(self, event):
        self.queue.append(event)
        self.events.append(event)
    
    def register(self, event_type, handler, ignore_self=False):
        pass
    
    def global_register(self, handler, ignore_self=False, is_senior=False):
        pass

class TestOKXMatcher:
    def setup_method(self):
        self.engine = MockEventEngine()
        self.symbol = "BTC-USDT"
        self.matcher = OKXMatcher(self.symbol)
        self.matcher.start(self.engine)
        
        # 初始化默认盘口
        self.matcher.best_bid_price_int = 100 * self.matcher.PRICE_SCALAR
        self.matcher.best_ask_price_int = 101 * self.matcher.PRICE_SCALAR

    # --- Helper Methods ---

    def create_ticker(self, bid, ask, bid_qty=1.0, ask_qty=1.0):
        ticker = OKXBookticker(symbol=self.symbol)
        ticker.bid_price_1 = bid
        ticker.bid_amount_1 = bid_qty
        ticker.ask_price_1 = ask
        ticker.ask_amount_1 = ask_qty
        for i in range(2, 6):
            setattr(ticker, f"bid_price_{i}", bid - i * 0.1)
            setattr(ticker, f"bid_amount_{i}", 1.0)
            setattr(ticker, f"ask_price_{i}", ask + i * 0.1)
            setattr(ticker, f"ask_amount_{i}", 1.0)
        return ticker

    def create_trade(self, price, size, side):
        return OKXTrades(symbol=self.symbol, price=price, size=size, side=side)

    def create_limit_order(self, price, qty, oid):
        order_id = int(oid)
        order = Order(order_id, Order.ORDER_TYPE_LIMIT, self.symbol, float(qty), float(price))
        order.state = Order.ORDER_STATE_SUBMITTED
        return order

    def test_01_limit_maker_entry(self):
        order = self.create_limit_order(99, 1.0, "1")
        self.matcher.on_order(order)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_RECEIVED
        assert len(self.matcher.buy_book) == 1

    def test_02_limit_taker_fill(self):
        order = self.create_limit_order(102, 1.0, "2")
        self.matcher.on_order(order)
        
        assert len(self.engine.queue) == 2
        evt_recv = self.engine.queue.popleft()
        evt_fill = self.engine.queue.popleft()
        assert evt_fill.state == Order.ORDER_STATE_FILLED
        assert evt_fill.filled_price == 101.0
        assert len(self.matcher.buy_book) == 0

    def test_03_trade_sweeping_passive(self):
        # 1. Maker Order at 100
        order = self.create_limit_order(100, 1.0, "3")
        self.matcher.on_order(order)
        
        # 必须发送包含价格 100 的 Ticker 以初始化 Rank
        ticker = self.create_ticker(100, 101, bid_qty=1.0)
        self.matcher.on_bookticker(ticker)
        
        self.engine.queue.clear()
        
        # 2. Trade Event: Seller Taker 砸到 99
        # 因为盘口显示 1.0，我们排在后面，所以需要 2.0 的量才能成交我们
        trade = self.create_trade(99, 2.5, 'sell')
        self.matcher.on_trade(trade)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_FILLED
        assert evt.order_id == 3

    def test_04_trade_logic_your_special_case(self):
        self.matcher.best_bid_price_int = 90 * self.matcher.PRICE_SCALAR
        self.matcher.best_ask_price_int = 100 * self.matcher.PRICE_SCALAR
        
        order = self.create_limit_order(95, 1.0, "4")
        self.matcher.on_order(order)
        
        # 确保订单被"看见"
        ticker = self.create_ticker(90, 100) # 这里不包含95，Rank 保持 10^9
        self.matcher.on_bookticker(ticker)
        
        self.engine.queue.clear()
        
        # 2. Trade: Buyer Taker 成交在 92 (Ask 掉到了 92)
        # 此时价格交叉，逻辑应该直接成交，无关排队
        trade = self.create_trade(92, 0.5, 'buy')
        self.matcher.on_trade(trade)
        
        assert len(self.engine.queue) == 1
        evt = self.engine.queue.pop()
        assert evt.state == Order.ORDER_STATE_FILLED
        assert evt.filled_price == 92.0

    def test_05_rank_queue_logic(self):
        # 1. 初始化盘口: Bid 100 (Size 1000)
        ticker = self.create_ticker(100, 101, bid_qty=1000, ask_qty=1000)
        self.matcher.on_bookticker(ticker)
        
        # 2. 下单 10 (Maker)
        order = self.create_limit_order(100, 10, "5")
        self.matcher.on_order(order)
        self.engine.queue.clear()
        
        # Rank 初始化 (排在 1000 后面)
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