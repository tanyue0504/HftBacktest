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
        matcher = OKXMatcher()
        
        # 组装
        matcher.start(engine)
        account.start(engine)
        
        return engine, account, matcher

    def create_ticker(self, mid_price, timestamp, qty=10.0):
        # 辅助创建 Ticker (Depth=25)
        # Bid = Mid - 0.5, Ask = Mid + 0.5
        bid = mid_price - 0.5
        ask = mid_price + 0.5
        
        ticker = OKXBookticker()
        ticker.symbol = SYMBOL
        ticker.timestamp = timestamp
        
        # 填充 Depth 1-25
        for i in range(1, 26):
            spread = (i-1) * 0.1
            setattr(ticker, f"bid_price_{i}", bid - spread)
            setattr(ticker, f"bid_amount_{i}", qty)
            setattr(ticker, f"ask_price_{i}", ask + spread)
            setattr(ticker, f"ask_amount_{i}", qty)
            
        return ticker

    def test_limit_order_queue_and_fill(self, setup_system):
        """
        集成测试核心场景：
        限价单排队 (Queueing) -> 被动成交 (Passive Fill) -> 账户结算
        """
        engine, account, matcher = setup_system
        
        # 1. 初始行情: Mid 50000.5 -> Bid 50000, Ask 50001
        ticker1 = self.create_ticker(50000.5, timestamp=1, qty=10.0)
        engine.put(ticker1)
        
        # 2. 策略下限价买单: 买入 1.0 BTC @ 50000
        order = Order.create_limit(SYMBOL, 1.0, 50000.0)
        order.state = Order.ORDER_STATE_SUBMITTED 
        engine.put(order)
        
        oid = order.order_id 
        
        # 3. 推送行情 (入册)
        engine.put(ticker1)
        
        # 验证入册
        assert oid in account.get_orders() 
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        # 4. 模拟成交 A: 卖出 5.0 (不足以吃掉前序队列)
        trade1 = OKXTrades(
            timestamp=2, symbol=SYMBOL, 
            trade_id=1001, price=50000.0, size=5.0, side="sell"
        )
        engine.put(trade1)
        
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        # 5. 模拟成交 B: 又卖出 6.0 (累计 11.0 > 10.0，触发成交)
        trade2 = OKXTrades(
            timestamp=3, symbol=SYMBOL, 
            trade_id=1002, price=50000.0, size=6.0, side="sell"
        )
        engine.put(trade2)
        
        # 验证：Position 应该变成 1.0
        assert account.get_positions().get(SYMBOL, 0) == 1.0
        
        # 【修复】订单成交后会从 active orders 移除，所以不能再 assert state
        # 而是确认它不在 active orders 里了
        assert oid not in account.get_orders()

    def test_market_order_immediate_fill(self, setup_system):
        """测试市价单立即成交"""
        engine, account, matcher = setup_system
        
        # 1. 行情
        ticker = self.create_ticker(50000.5, timestamp=1, qty=100.0)
        engine.put(ticker)
        
        # 2. 下市价卖单
        # 【修复】卖出应该是负数 quantity
        order = Order.create_market(SYMBOL, -0.5) 
        order.state = Order.ORDER_STATE_SUBMITTED
        engine.put(order)
        oid = order.order_id
        
        # 3. 再次推行情触发撮合
        engine.put(ticker)
        
        # 4. 验证
        assert account.get_positions().get(SYMBOL, 0) == -0.5
        # 同样，成交后 active orders 为空
        assert oid not in account.get_orders()