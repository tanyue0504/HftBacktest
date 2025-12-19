import pytest
from hft_backtest import EventEngine, Order
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.matcher import OKXMatcher
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXFundingRate, OKXDelivery

# 常量配置
SYMBOL = "BTC-USDT-SWAP"
SCALER = Order.SCALER

class TestOKXIntegration:
    
    @pytest.fixture
    def setup_system(self):
        """
        搭建集成测试环境：
        EventEngine <--> OKXAccount (Server)
                     <--> OKXMatcher (Server)
        """
        engine = EventEngine()
        
        # 1. 初始化组件
        # 初始资金 100,000 USDT
        account = OKXAccount(initial_balance=100000.0) 
        # 费率: Taker 5bps, Maker 2bps
        matcher = OKXMatcher(taker_fee=0.0005, maker_fee=0.0002)
        
        # 2. 注册到引擎 (绑定事件监听)
        account.start(engine)
        matcher.start(engine)
        
        return engine, account, matcher

    def create_ticker(self, mid_price, timestamp=0, qty=10.0):
        """
        辅助函数：生成简单的 Bookticker
        Ask1 = mid_price + 0.5
        Bid1 = mid_price - 0.5
        """
        return OKXBookticker(
            timestamp=timestamp,
            symbol=SYMBOL,
            ask_price_1=mid_price + 0.5, ask_amount_1=qty,
            bid_price_1=mid_price - 0.5, bid_amount_1=qty,
            # 其他档位保持默认 0
        )

    def test_limit_order_queue_and_fill(self, setup_system):
        """
        集成测试核心场景：
        限价单排队 (Queueing) -> 被动成交 (Passive Fill) -> 账户结算
        """
        engine, account, matcher = setup_system
        
        # 1. 初始行情: Mid 50000.5 -> Bid 50000, Ask 50001
        # 盘口挂单量均为 10.0
        ticker1 = self.create_ticker(50000.5, timestamp=1, qty=10.0)
        engine.put(ticker1)
        
        # 2. 策略下限价买单: 买入 1.0 BTC @ 50000 (跟盘口价一致，做 Maker)
        order = Order(
            order_id=1, order_type=OrderType.LIMIT_ORDER, 
            symbol=SYMBOL, quantity=1.0, price=50000.0, 
            state=OrderState.SUBMITTED # 模拟策略已发出
        )
        engine.put(order)
        
        # 3. 推送下一笔行情 -> 触发 Matcher 入书
        # Matcher 会计算 Rank：
        # 价格 50000 此时是 Bid1，且盘口已有 10.0 的量。
        # 所以 Order.rank = 10.0 (排在 10 个币后面)
        engine.put(ticker1)
        
        # 验证：订单已在账户活跃列表中
        assert 1 in account.get_orders()
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        # 4. 模拟成交 A: 有人卖出 5.0 个币 (Trade Side=Sell)
        # 这不足以吃掉前面的排队量 (10.0)，所以我的订单不应该成交
        trade1 = OKXTrades(
            timestamp=2, symbol=SYMBOL, 
            trade_id="t1", price=50000.0, size=5.0, side="sell"
        )
        engine.put(trade1)
        
        # 验证：尚未成交
        assert 1 in account.get_orders()
        assert account.get_positions().get(SYMBOL, 0) == 0
        
        # 5. 模拟成交 B: 有人大单砸盘，卖出 6.0 个币
        # 累计成交 = 5.0 + 6.0 = 11.0
        # 超过了排队量 10.0，我的订单 (size 1.0) 应该成交
        trade2 = OKXTrades(
            timestamp=3, symbol=SYMBOL, 
            trade_id="t2", price=50000.0, size=6.0, side="sell"
        )
        engine.put(trade2)
        
        # 验证：完全成交
        # Account 收到 FILLED 事件
        # Position = +1.0
        # Balance = 100000 - (1.0 * 50000) - Fee
        # Fee = 50000 * 0.0002 (Maker) = 10.0
        assert account.get_positions()[SYMBOL] == pytest.approx(1.0)
        assert account.get_balance() == pytest.approx(100000.0 - 50000.0 - 10.0)
        assert 1 not in account.order_dict

    def test_market_order_execution(self, setup_system):
        """测试：市价单 (Taker) 立即成交"""
        engine, account, matcher = setup_system
        
        # 行情: Bid 50000, Ask 50001
        ticker = self.create_ticker(50000.5)
        engine.put(ticker)
        
        # 下市价买单 1.0 BTC (应以 Ask 50001 成交)
        order = Order(
            order_id=2, order_type=OrderType.MARKET_ORDER,
            symbol=SYMBOL, quantity=1.0, price=None,
            state=OrderState.SUBMITTED
        )
        engine.put(order)
        
        # 触发撮合 (Pending -> Fill)
        engine.put(ticker)
        
        # 验证
        # Price = 50001
        # CashFlow = -1 * 1.0 * 50001 = -50001
        # Fee (Taker) = 50001 * 0.0005 = 25.0005
        assert account.get_positions()[SYMBOL] == pytest.approx(1.0)
        expected_balance = 100000.0 - 50001.0 - 25.0005
        assert account.get_balance() == pytest.approx(expected_balance)

    def test_cancel_order_logic(self, setup_system):
        """测试：挂单后撤单，验证系统状态一致性"""
        engine, account, matcher = setup_system
        ticker = self.create_ticker(50000.5)
        engine.put(ticker)
        
        # 1. 挂买单 40000 (深价位，不成交)
        order = Order(
            order_id=3, order_type=OrderType.LIMIT_ORDER,
            symbol=SYMBOL, quantity=1.0, price=40000.0,
            state=OrderState.SUBMITTED
        )
        engine.put(order)
        engine.put(ticker) # 入书
        
        assert 3 in account.order_dict
        
        # 2. 发送撤单指令
        # Cancel Order 工厂方法通常不带 Symbol，但 Matcher 需要能在内部索引中找到它
        cancel = Order.cancel_order(target_order_id=3)
        engine.put(cancel)
        
        # 3. 验证
        # Matcher 处理撤单 -> 推送 CANCELED -> Account 移除订单
        assert 3 not in account.order_dict
        # 余额无变化
        assert account.get_balance() == 100000.0

    def test_funding_and_delivery_lifecycle(self, setup_system):
        """
        测试：资金费率结算 -> 交割平仓 的全流程
        验证 Account 的现金流计算是否正确
        """
        engine, account, matcher = setup_system
        
        # 1. 初始持仓：通过市价单买入 1.0 BTC @ 50001
        ticker = self.create_ticker(50000.5)
        engine.put(ticker)
        
        o = Order(4, OrderType.MARKET_ORDER, SYMBOL, 1.0, None, OrderState.SUBMITTED)
        engine.put(o)
        engine.put(ticker) 
        
        # 记录开仓后的余额
        # Balance = 100000 - 50001 - 25.0005 (Taker Fee) = 49973.9995
        balance_post_trade = account.get_balance()
        assert account.get_positions()[SYMBOL] == 1.0
        
        # 2. 资金费率结算
        # 假设：Funding Rate = 0.01% (万一), 标记价格 = 50000
        # Long 仓位支付资金费: 1.0 * 50000 * 0.0001 = 5.0 USDT
        funding = OKXFundingRate(
            timestamp=100, symbol=SYMBOL, 
            funding_rate=0.0001, price=50000.0
        )
        engine.put(funding)
        
        balance_post_funding = balance_post_trade - 5.0
        assert account.get_balance() == pytest.approx(balance_post_funding)
        
        # 3. 交割平仓
        # 假设交割价 = 52000 (盈利)
        # 平仓带来的 CashFlow = 1.0 * 52000 = +52000
        delivery = OKXDelivery(timestamp=200, symbol=SYMBOL, price=52000.0)
        engine.put(delivery)
        
        # 验证
        # 1. 仓位被移除
        assert SYMBOL not in account.get_positions()
        
        # 2. 最终余额
        # Final = Previous + 52000
        assert account.get_balance() == pytest.approx(balance_post_funding + 52000.0)
        
        # 3. Matcher 内部状态清理 (OrderBook 应为空)
        # 我们可以通过再发一个撤单来看看是否报错，或者侵入式检查
        assert SYMBOL not in matcher.order_book

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__]))