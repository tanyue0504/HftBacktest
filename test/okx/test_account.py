import pytest
from unittest.mock import MagicMock
from collections import namedtuple

from hft_backtest import EventEngine, Order, OrderState, OrderType
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.event import OKXTrades, OKXFundingRate, OKXDelivery

# --- 模拟数据结构 (根据你 event.py 的定义) ---
# 假设 data 属性是 namedtuple 或对象，包含必要字段
MockTradeData = namedtuple('MockTradeData', ['symbol', 'price'])
MockFundingData = namedtuple('MockFundingData', ['symbol', 'price', 'funding_rate'])
MockDeliveryData = namedtuple('MockDeliveryData', ['symbol', 'price'])

class TestOKXAccount:
    
    @pytest.fixture
    def account(self):
        """每个测试用例前初始化一个新的 Account"""
        acc = OKXAccount(initial_balance=10000.0)
        # 模拟 Engine，因为 account.start() 会用到
        engine = MagicMock(spec=EventEngine)
        acc.start(engine)
        return acc

    def create_filled_order(self, order_id, symbol, side, price, qty, fee=0.0):
        """辅助函数：创建一个已成交的订单"""
        # side: 'buy' -> qty > 0, 'sell' -> qty < 0
        quantity = qty if side == 'buy' else -qty
        
        order = Order(
            order_id=order_id,
            order_type=OrderType.LIMIT_ORDER,
            symbol=symbol,
            quantity=quantity,
            price=price,
            state=OrderState.FILLED,
            filled_price=price,
            commission_fee=fee
        )
        return order

    def test_buy_order_impact(self, account):
        """测试买单成交：现金流出，持仓增加"""
        # 1. 模拟买入 1 BTC @ 50,000, 手续费 10
        order = self.create_filled_order(1, "BTC-USDT", 'buy', 50000.0, 1.0, fee=10.0)
        account.on_order(order)

        # 验证余额: 10000 - 50000(买入花费) - 10(手续费) = -40010
        # 注：全仓模式下余额变成负数代表占用了本金或产生了负债，
        # 真正的净值要看 Equity
        assert account.cash_balance == 10000.0 - 50000.0 - 10.0
        
        # 验证持仓
        assert account.get_positions()["BTC-USDT"] == 1.0
        
        # 验证累计手续费
        assert account.get_cumulative_commission("BTC-USDT") == 10.0

    def test_equity_calculation(self, account):
        """测试权益计算 (浮动盈亏)"""
        symbol = "BTC-USDT"
        
        # 1. 初始买入 1 BTC @ 50,000
        order = self.create_filled_order(1, symbol, 'buy', 50000.0, 1.0)
        account.on_order(order)
        # 此时 Balance = -40000, 持仓 1 BTC
        
        # 2. 推送行情：价格涨到 51,000
        trade_data = MockTradeData(symbol=symbol, price=51000.0)
        event = OKXTrades(timestamp=1000, name="trades", data=trade_data)
        account.on_trade_data(event)

        # 3. 验证权益
        # Equity = Balance + MarketValue
        #        = -40000 + (1 * 51000) = 11000
        # 初始本金 10000，赚了 1000，正确。
        assert account.get_equity() == 11000.0

    def test_funding_fee_settlement(self, account):
        """测试资金费率结算"""
        symbol = "ETH-USDT"
        
        # 1. 持仓 10 ETH, 当前价格 3000
        order = self.create_filled_order(1, symbol, 'buy', 3000.0, 10.0)
        account.on_order(order)
        # 更新最新价以便计算资金费
        account.price_dict[symbol] = 3000.0 
        
        prev_balance = account.cash_balance

        # 2. 收到资金费率事件: 费率 0.01% (0.0001)
        # 费用 = 持仓(10) * 价格(3000) * 费率(0.0001) = 3.0 U
        fund_data = MockFundingData(symbol=symbol, price=3000.0, funding_rate=0.0001)
        event = OKXFundingRate(timestamp=2000, name="funding", data=fund_data)
        
        account.on_funding_data(event)

        # 3. 验证余额减少
        expected_fee = 10 * 3000 * 0.0001
        assert account.cash_balance == prev_balance - expected_fee
        assert account.get_cumulative_funding_fee(symbol) == expected_fee

    def test_round_trip_pnl(self, account):
        """测试开平仓完整流程 (Round Trip)"""
        symbol = "BTC-USDT"
        
        # 1. 开仓买入 1 BTC @ 50,000
        o1 = self.create_filled_order(1, symbol, 'buy', 50000.0, 1.0)
        account.on_order(o1)
        
        # 2. 平仓卖出 1 BTC @ 55,000
        o2 = self.create_filled_order(2, symbol, 'sell', 55000.0, 1.0)
        account.on_order(o2)

        # 3. 验证
        # 持仓应为 0
        assert account.get_positions().get(symbol, 0) == 0
        
        # 现金流 Balance:
        # 初始 10000
        # 买入: -50000
        # 卖出: +55000
        # 最终: 15000
        assert account.cash_balance == 15000.0
        
        # 累计交易盈亏 (Trade PnL)
        # -50000 + 55000 = 5000
        assert account.get_cumulative_trade_pnl(symbol) == 5000.0

    def test_delivery_liquidation(self, account):
        """测试交割强平"""
        symbol = "BTC-USDT-240329"
        
        # 1. 持仓 2 BTC @ 60,000
        account.on_order(self.create_filled_order(1, symbol, 'buy', 60000.0, 2.0))
        
        # 2. 触发交割事件，交割价 62,000
        delivery_data = MockDeliveryData(symbol=symbol, price=62000.0)
        event = OKXDelivery(timestamp=3000, name="delivery", data=delivery_data)
        
        account.on_delivery_data(event)
        
        # 3. 验证
        # 持仓被强制清零
        assert symbol not in account.get_positions()
        
        # 余额应增加平仓价值: 2 * 62000 = 124000
        # 之前的 Balance 是 10000 - 120000 = -110000
        # 交割后 Balance = -110000 + 124000 = 14000
        # 净赚 4000
        assert account.cash_balance == 10000.0 - 120000.0 + 124000.0