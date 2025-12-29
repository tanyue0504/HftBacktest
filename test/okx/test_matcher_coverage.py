import pytest
import sys
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.event_engine import EventEngine
from hft_backtest.okx.event import OKXBookticker, OKXTrades
from hft_backtest.order import (
    Order, 
    ORDER_STATE_RECEIVED, 
    ORDER_STATE_FILLED, 
    ORDER_STATE_CANCELED, 
    ORDER_STATE_SUBMITTED,
    ORDER_TYPE_CANCEL,
    ORDER_TYPE_TRACKING,
    ORDER_TYPE_LIMIT
)

# 辅助函数：快速创建行情
def create_ticker(symbol="BTC-USDT", bid_start=50000, ask_start=50001, gap=1, vol=1.0):
    ticker = OKXBookticker(timestamp=100, symbol=symbol)
    for i in range(25):
        ask_p = ask_start + i * gap
        bid_p = bid_start - i * gap
        setattr(ticker, f"ask_price_{i+1}", float(ask_p))
        setattr(ticker, f"ask_amount_{i+1}", vol)
        setattr(ticker, f"bid_price_{i+1}", float(bid_p))
        setattr(ticker, f"bid_amount_{i+1}", vol)
    return ticker

class TestOKXMatcherCoverage:
    
    @pytest.fixture
    def setup(self):
        matcher = OKXMatcher("BTC-USDT")
        engine = EventEngine()
        captured_events = []
        engine.global_register(lambda e: captured_events.append(e))
        matcher.start(engine)
        return matcher, engine, captured_events

    def test_race_condition_cancel_before_new(self, setup):
        """测试先撤单后下单的情况"""
        matcher, _, events = setup
        
        # 1. 撤单指令先到达 -> 静默失败
        # 工厂函数不提供 Create Cancel，需手动或 derive，这里手动构造指令
        cancel_cmd = Order(100, ORDER_TYPE_CANCEL, "BTC-USDT", 0, 0)
        matcher.on_order(cancel_cmd)
        assert len(events) == 0
        assert len(matcher.buy_book) == 0
        
        # 2. 订单后到
        new_order = Order.create_limit("BTC-USDT", 1.0, 50000)
        new_order.order_id = 100
        new_order.state = ORDER_STATE_SUBMITTED
        
        matcher.on_bookticker(create_ticker(bid_start=50000, ask_start=50001))
        matcher.on_order(new_order)
        assert len(events) == 1
        assert events[0].state == ORDER_STATE_RECEIVED

    def test_search_tree_ask_coverage(self, setup):
        """覆盖 _search_ask_book 的所有分支"""
        matcher, _, _ = setup
        # Ask Prices: 100, 102, ... 148 (Indices 0..24)
        ticker = create_ticker(bid_start=90, ask_start=100, gap=2)
        matcher.on_bookticker(ticker)
        
        def check_rank(price):
            o = Order.create_limit("BTC-USDT", -1.0, price)
            o.state = ORDER_STATE_SUBMITTED
            o.rank = 1000.0
            matcher.sell_book.append(o)
            matcher.on_bookticker(ticker)
            return matcher.sell_book[0].rank

        # Hit (Root): Ask13=124. Volume=1.0. Rank=1.0
        assert check_rank(124) == 1.0
        matcher.sell_book.clear()

        # Boundary Cross (<100) -> Gap -> 0.0
        assert check_rank(99) == 0.0
        matcher.sell_book.clear()

        # Boundary Tail (>148) -> Tail -> 1000.0 (Rank unchanged)
        assert check_rank(150) == 1000.0
        matcher.sell_book.clear()

        # Gap (101)
        assert check_rank(101) == 0.0
        matcher.sell_book.clear()

        # Left Side Hits
        for p in [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122]:
            assert check_rank(p) == 1.0
            matcher.sell_book.clear()

        # Right Side Hits
        for p in [126, 128, 130, 132, 134, 136, 138, 140, 142, 144, 146, 148]:
            assert check_rank(p) == 1.0
            matcher.sell_book.clear()

    def test_search_tree_bid_coverage(self, setup):
        """覆盖 _search_bid_book (降序)"""
        matcher, _, _ = setup
        # Bid Prices: 100, 98, ... 52
        ticker = create_ticker(bid_start=100, ask_start=200, gap=2)
        matcher.on_bookticker(ticker)
        
        def check_rank(price):
            o = Order.create_limit("BTC-USDT", 1.0, price)
            o.state = ORDER_STATE_SUBMITTED
            o.rank = 1000.0
            matcher.buy_book.append(o)
            matcher.on_bookticker(ticker)
            return matcher.buy_book[0].rank

        # Hit
        assert check_rank(100) == 1.0
        matcher.buy_book.clear()
        assert check_rank(52) == 1.0
        matcher.buy_book.clear()

        # Cross (>100)
        assert check_rank(101) == 0.0
        matcher.buy_book.clear()

        # Tail (<52)
        assert check_rank(50) == 1000.0
        matcher.buy_book.clear()

    def test_tracking_order_conversion(self, setup):
        matcher, _, events = setup
        
        # 1. 有盘口 -> 正常转换
        matcher.on_bookticker(create_ticker(bid_start=50000, ask_start=50001))
        o = Order(1, ORDER_TYPE_TRACKING, "BTC-USDT", 1.0, 0.0)
        o.state = ORDER_STATE_SUBMITTED
        matcher.on_order(o)
        
        assert events[0].state == ORDER_STATE_RECEIVED
        assert events[0].price == 50000.0
        
        # 2. 无盘口 (Max Ask) -> 忽略 (无事件)
        events.clear()
        matcher2 = OKXMatcher("BTC-USDT")
        
        # 【修复点】使用真实的 EventEngine 替代 MockEngine
        # 因为 Cython 的 start 方法强制检查参数类型是否为 hft_backtest.event_engine.EventEngine
        engine2 = EventEngine()
        captured_events2 = []
        engine2.global_register(lambda e: captured_events2.append(e))
        matcher2.start(engine2)
        
        o_sell = Order.create_tracking("BTC-USDT", -1.0)
        o_sell.state = ORDER_STATE_SUBMITTED
        # 直接调用而非通过引擎推送导致监听器无法收到事件
        # 因此理论上只会收到matcher收到后推送的receied事件
        matcher2.on_order(o_sell)
        
        assert len(captured_events2) == 1
        assert captured_events2[0].is_received

    def test_trade_execution(self, setup):
        matcher, _, events = setup
        # 设置大一点的盘口量 (100.0)，防止挂单(1.0)直接被盘口消化（虽然这里价格是 Ask2，不会立即成交）
        ticker = create_ticker(bid_start=50000, ask_start=50001, vol=100.0)
        matcher.on_bookticker(ticker)
        
        # 挂单 Sell @ 50002 (Ask2)
        s1 = Order.create_limit("BTC-USDT", -1.0, 50001)
        s1.state = ORDER_STATE_SUBMITTED
        matcher.on_order(s1)
        
        # 刷新 Rank -> 前面有 Ask2 的 100.0 量 -> Rank=100.0
        matcher.on_bookticker(ticker)
        assert matcher.sell_book[0].rank == 100.0
        
        events.clear()
        # Trade 100.0 @ 50002. Matches Rank 100.0 -> Fill
        trade = OKXTrades(timestamp=200, symbol="BTC-USDT", price=50002.0, size=100.0, side="buy")
        matcher.on_trade(trade)
        
        assert len(events) == 1
        assert events[0].state == ORDER_STATE_FILLED

    def test_rounding_logic(self, setup):
        matcher, _, _ = setup
        assert matcher.to_int_price(100.5) == 10050000000

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))