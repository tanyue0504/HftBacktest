import pytest
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.okx.event import OKXTrades, OKXBookticker
from hft_backtest import Order

ORDER_TYPE_LIMIT = Order.ORDER_TYPE_LIMIT
ORDER_TYPE_CANCEL = Order.ORDER_TYPE_CANCEL
ORDER_STATE_FILLED = Order.ORDER_STATE_FILLED
ORDER_STATE_CANCELED = Order.ORDER_STATE_CANCELED
ORDER_STATE_SUBMITTED = Order.ORDER_STATE_SUBMITTED

class MockEngine:
    def __init__(self):
        self.events = []
    
    def put(self, event):
        self.events.append(event)
        
    def register(self, event_type, handler):
        pass

@pytest.fixture
def matcher_env():
    matcher = OKXMatcher()
    engine = MockEngine()
    matcher.start(engine)
    return matcher, engine

def create_ticker(symbol, bid, ask):
    ticker = OKXBookticker()
    ticker.symbol = symbol
    for i in range(1, 26):
        setattr(ticker, f"bid_price_{i}", bid - (i-1)*0.1)
        setattr(ticker, f"bid_amount_{i}", 1.0)
        setattr(ticker, f"ask_price_{i}", ask + (i-1)*0.1)
        setattr(ticker, f"ask_amount_{i}", 1.0)
    return ticker

def test_matcher_limit_buy_full_fill(matcher_env):
    """测试限价买单作为 Maker 被 Taker 卖单吃掉"""
    matcher, engine = matcher_env
    matcher.on_bookticker(create_ticker("BTC-USDT", 49000.0, 51000.0))
    
    order = Order.create_limit("BTC-USDT", 1.0, 50000.0)
    order.order_id = 1
    order.state = ORDER_STATE_SUBMITTED
    matcher.on_order(order)
    
    matcher.on_bookticker(create_ticker("BTC-USDT", 49000.0, 51000.0))
    
    trade = OKXTrades()
    trade.symbol = "BTC-USDT"
    trade.price = 49900.0
    trade.size = 2.0 
    trade.side = "sell" 
    
    matcher.on_trade(trade) 
    
    order_events = [e for e in engine.events if isinstance(e, Order)]
    last_event = order_events[-1]
    
    assert last_event.order_id == 1
    # 只要检查状态为 FILLED 即代表全成
    assert last_event.state == ORDER_STATE_FILLED
    # 【修正】不再检查 traded 字段，因为它是内部排队计数器

def test_matcher_limit_sell_crossing_fill(matcher_env):
    """测试卖单被买单向上穿价吃掉 (应完全成交)"""
    matcher, engine = matcher_env
    
    matcher.on_bookticker(create_ticker("BTC-USDT", 59000.0, 61000.0))
    
    # 卖单 @ 60000，数量 2.0
    order = Order.create_limit("BTC-USDT", -2.0, 60000.0)
    order.order_id = 2
    order.state = ORDER_STATE_SUBMITTED
    matcher.on_order(order)
    
    matcher.on_bookticker(create_ticker("BTC-USDT", 59000.0, 61000.0))
    
    # 市场买单 @ 60001 (穿过了 60000)
    # 在 All-or-Nothing 框架下，穿价即全成
    trade = OKXTrades()
    trade.symbol = "BTC-USDT"
    trade.price = 60001.0 
    trade.size = 0.5 
    trade.side = "buy" 
    
    matcher.on_trade(trade)
    
    order_events = [e for e in engine.events if isinstance(e, Order)]
    last_event = order_events[-1]
    assert last_event.order_id == 2
    
    # 检查全成状态
    assert last_event.state == ORDER_STATE_FILLED

def test_matcher_cancel_order(matcher_env):
    matcher, engine = matcher_env
    matcher.on_bookticker(create_ticker("BTC-USDT", 9000.0, 11000.0))
    
    order = Order.create_limit("BTC-USDT", 1.0, 10000.0)
    order.order_id = 3
    order.state = ORDER_STATE_SUBMITTED
    matcher.on_order(order)
    
    matcher.on_bookticker(create_ticker("BTC-USDT", 9000.0, 11000.0))
    
    cancel = order.derive()
    cancel.order_type = ORDER_TYPE_CANCEL
    matcher.on_order(cancel)
    
    target_events = [e for e in engine.events if isinstance(e, Order) and e.order_id == 3 and e.state == ORDER_STATE_CANCELED]
    assert len(target_events) > 0

def test_matcher_symbol_mismatch(matcher_env):
    matcher, engine = matcher_env
    matcher.on_bookticker(create_ticker("BTC-USDT", 49000.0, 51000.0))
    
    order = Order.create_limit("BTC-USDT", 1.0, 50000.0)
    order.state = ORDER_STATE_SUBMITTED
    matcher.on_order(order)
    
    matcher.on_bookticker(create_ticker("BTC-USDT", 49000.0, 51000.0))
    
    trade = OKXTrades()
    trade.symbol = "ETH-USDT"
    trade.price = 4000
    trade.size = 100
    matcher.on_trade(trade)
    
    order_events = [e for e in engine.events if isinstance(e, Order) and e.order_id == order.order_id]
    for e in order_events:
        # 既没成交，也没状态变化
        assert e.state != ORDER_STATE_FILLED