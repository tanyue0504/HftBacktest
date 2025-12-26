import pytest
from hft_backtest.event_engine import EventEngine
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.okx.event import OKXBookticker, OKXTrades
from hft_backtest import Order

SYMBOL = "BTC-USDT-SWAP"

class TestOKXIntegration:
    
    @pytest.fixture
    def setup_system(self):
        engine = EventEngine()
        account = OKXAccount(initial_balance=100000)
        # 确保传入正确的 symbol
        matcher = OKXMatcher(SYMBOL)
        
        matcher.start(engine)
        account.start(engine)
        
        return engine, account, matcher

    def create_ticker(self, mid_price, timestamp, qty=10.0):
        bid = mid_price - 0.5
        ask = mid_price + 0.5
        ticker = OKXBookticker()
        ticker.symbol = SYMBOL
        ticker.timestamp = timestamp
        
        for i in range(1, 26):
            spread = (i-1) * 0.1
            setattr(ticker, f"bid_price_{i}", bid - spread)
            setattr(ticker, f"bid_amount_{i}", qty)
            setattr(ticker, f"ask_price_{i}", ask + spread)
            setattr(ticker, f"ask_amount_{i}", qty)
            
        return ticker

    def test_limit_order_queue_and_fill(self, setup_system):
        engine, account, matcher = setup_system
        
        ticker1 = self.create_ticker(50000.5, timestamp=1, qty=10.0)
        engine.put(ticker1)
        
        order = Order.create_limit(SYMBOL, 1.0, 50000.0)
        order.state = Order.ORDER_STATE_SUBMITTED 
        engine.put(order)
        
        oid = order.order_id 
        engine.put(ticker1)
        
        assert oid in account.get_orders() 
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        trade1 = OKXTrades(
            timestamp=2, symbol=SYMBOL, 
            trade_id=1001, price=50000.0, size=5.0, side="sell"
        )
        engine.put(trade1)
        
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        # 累计成交 11.0 > 10.0 (Book Qty) + 1.0 (My Order)? 
        # 只要超过前面的 10.0 即可
        trade2 = OKXTrades(
            timestamp=3, symbol=SYMBOL, 
            trade_id=1002, price=50000.0, size=6.0, side="sell"
        )
        engine.put(trade2)
        
        assert account.get_positions().get(SYMBOL, 0) == 1.0
        assert oid not in account.get_orders()

    def test_market_order_immediate_fill(self, setup_system):
        engine, account, matcher = setup_system
        
        ticker = self.create_ticker(50000.5, timestamp=1, qty=100.0)
        engine.put(ticker)
        
        order = Order.create_market(SYMBOL, -0.5) 
        order.state = Order.ORDER_STATE_SUBMITTED
        engine.put(order)
        oid = order.order_id
        
        engine.put(ticker)
        
        assert account.get_positions().get(SYMBOL, 0) == -0.5
        assert oid not in account.get_orders()