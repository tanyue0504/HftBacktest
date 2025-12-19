import pytest
from unittest.mock import MagicMock
from hft_backtest import Order, EventEngine
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXDelivery

# 假设 Order.SCALER 是 1e8
SCALER = Order.SCALER

class TestOKXMatcher:
    
    @pytest.fixture
    def engine(self):
        """Mock 事件引擎，用于捕获撮合结果"""
        engine = MagicMock(spec=EventEngine)
        engine.put = MagicMock()
        return engine

    @pytest.fixture
    def matcher(self, engine):
        matcher = OKXMatcher(taker_fee=0.0005, maker_fee=0.0002)
        matcher.start(engine)
        return matcher

    def create_ticker(self, symbol, best_bid, best_ask, qty=1.0):
        """辅助函数：创建扁平的 OKXBookticker 对象"""
        # 利用修改后带有默认参数的构造函数
        ticker = OKXBookticker(timestamp=1, symbol=symbol)
        
        # 填充 25 档行情
        for i in range(1, 26):
            # Bid: 递减 (100, 99, 98...)
            setattr(ticker, f"bid_price_{i}", best_bid - (i-1))
            setattr(ticker, f"bid_amount_{i}", qty)
            
            # Ask: 递增 (101, 102, 103...)
            setattr(ticker, f"ask_price_{i}", best_ask + (i-1))
            setattr(ticker, f"ask_amount_{i}", qty)
            
        return ticker

    def test_limit_buy_maker(self, matcher, engine):
        """测试：限价买单挂单 (Maker)"""
        symbol = "BTC-USDT"
        
        # 1. 初始行情: Bid 100, Ask 105
        ticker = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker) 

        # 2. 下单: 买单 101 (优于当前 Bid 100, 但低于 Ask 105 -> 挂单)
        order = self.create_order(1, symbol, 1, 1.0, 101.0)
        matcher.on_order(order)

        # 3. 再次推送行情触发撮合
        matcher.on_bookticker(ticker)

        # 验证: 订单应在 order_book 中
        assert symbol in matcher.order_book
        book = matcher.order_book[symbol][matcher.SIDE_BUY]
        price_int = matcher.to_int_price(101.0)
        assert price_int in book
        assert 1 in book[price_int]
        
        # 检查 engine 调用: 收到 RECEIVED 状态
        args, _ = engine.put.call_args
        assert args[0].state == OrderState.RECEIVED

    def test_limit_buy_taker(self, matcher, engine):
        """测试：限价买单吃单 (Taker)"""
        symbol = "BTC-USDT"
        ticker = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker)

        # 2. 下单: 买单 106 (高于 Ask 105 -> 立即成交)
        order = self.create_order(1, symbol, 1, 0.5, 106.0)
        matcher.on_order(order)

        # 3. 触发撮合
        matcher.on_bookticker(ticker)

        # 验证: engine 应收到 FILLED 事件
        calls = engine.put.call_args_list
        filled_event = calls[-1][0][0]
        
        assert filled_event.state == OrderState.FILLED
        assert filled_event.filled_price == 105.0
        assert filled_event.commission_fee == (105.0 * 0.5) * matcher.taker_fee

    def test_limit_sell_maker_then_fill(self, matcher, engine):
        """测试：卖单挂单后，行情移动导致成交 (Passive Fill)"""
        symbol = "BTC-USDT"
        
        ticker1 = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker1)

        # 2. 下卖单 102 (挂在中间)
        order = self.create_order(1, symbol, -1, 1.0, 102.0)
        matcher.on_order(order)
        matcher.on_bookticker(ticker1) # 处理入队

        # 验证已挂单
        assert matcher.to_int_price(102.0) in matcher.order_book[symbol][matcher.SIDE_SELL]

        # 3. 行情剧烈波动: Bid 涨到 103 (Crossed Market)
        ticker2 = self.create_ticker(symbol, 103.0, 108.0)
        matcher.on_bookticker(ticker2)

        # 验证: 被动成交, Maker Fee
        filled_event = engine.put.call_args[0][0]
        assert filled_event.state == OrderState.FILLED
        assert filled_event.filled_price == 102.0
        assert filled_event.commission_fee == (102.0 * 1.0) * matcher.maker_fee
        assert len(matcher.order_book[symbol][matcher.SIDE_SELL]) == 0

    def test_market_buy(self, matcher, engine):
        """测试：市价买单"""
        symbol = "BTC-USDT"
        ticker = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker)

        # 市价买入
        order = self.create_order(1, symbol, 1, 1.0, type=OrderType.MARKET_ORDER)
        matcher.on_order(order)
        matcher.on_bookticker(ticker)

        # 验证: 以 Ask 1 (105.0) 成交
        filled_event = engine.put.call_args[0][0]
        assert filled_event.state == OrderState.FILLED
        assert filled_event.filled_price == 105.0

    def test_cancel_order(self, matcher, engine):
        """测试：撤单逻辑"""
        symbol = "BTC-USDT"
        ticker = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker)

        # 1. 挂买单 99
        order = self.create_order(1, symbol, 1, 1.0, 99.0)
        matcher.on_order(order)
        matcher.on_bookticker(ticker)
        assert matcher.to_int_price(99.0) in matcher.order_book[symbol][matcher.SIDE_BUY]

        # 2. 发送撤单指令
        cancel_order = Order.cancel_order(target_order_id=1)
        matcher.on_order(cancel_order) 

        # 验证: 收到 CANCELED 事件
        canceled_event = engine.put.call_args[0][0]
        assert canceled_event.state == OrderState.CANCELED
        assert canceled_event.order_id == 1
        assert len(matcher.order_book[symbol][matcher.SIDE_BUY][matcher.to_int_price(99.0)]) == 0

    def test_trade_event_matching(self, matcher, engine):
        """测试：Trade 事件触发被动成交"""
        symbol = "BTC-USDT"
        # 1. 挂买单 100
        order = self.create_order(1, symbol, 1, 1.0, 100.0)
        matcher.on_order(order)
        
        # 先推一个 Bookticker 让订单入书
        ticker = self.create_ticker(symbol, 99.0, 101.0)
        matcher.on_bookticker(ticker)
        
        # 2. 模拟市场发生一笔成交: 价格 100, Side=Sell (主动卖方砸盘)
        trade = OKXTrades(timestamp=2, symbol=symbol, price=100.0, size=0.5, side='sell')
        
        matcher.on_trade(trade)

        # 验证: 订单被成交
        filled_event = engine.put.call_args[0][0]
        assert filled_event.state == OrderState.FILLED
        assert filled_event.filled_price == 100.0
        assert filled_event.commission_fee == (100.0 * 1.0) * matcher.maker_fee

    def test_tracking_order(self, matcher, engine):
        """测试：Tracking Order 转换为 Limit Order"""
        symbol = "BTC-USDT"
        ticker = self.create_ticker(symbol, 100.0, 105.0)
        matcher.on_bookticker(ticker)

        # 下一个 Buy Tracking Order (应该挂在 Bid 1 = 100)
        order = self.create_order(1, symbol, 1, 1.0, type=OrderType.TRACKING_ORDER)
        matcher.on_order(order)
        matcher.on_bookticker(ticker)

        # 验证: 订单进入 Order Book, 价格为 100.0
        price_int = matcher.to_int_price(100.0)
        assert price_int in matcher.order_book[symbol][matcher.SIDE_BUY]
        
        stored_order = matcher.order_book[symbol][matcher.SIDE_BUY][price_int][1]
        assert stored_order.price == 100.0
        assert stored_order.order_type == OrderType.LIMIT_ORDER

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__]))