import pytest
from unittest.mock import MagicMock
from hft_backtest import Order, OrderState, EventEngine
from hft_backtest.okx.account import OKXAccount
from hft_backtest.okx.event import OKXTrades, OKXFundingRate, OKXDelivery
from hft_backtest.order import OrderType

# 假设 Order.SCALER 是 1e7 (根据之前的上下文)
# 如果实际值不同，测试会自动适配引用 Order.SCALER
SCALER = Order.SCALER 

class TestOKXAccount:
    
    @pytest.fixture
    def account(self):
        """创建一个初始资金为 10,000 USDT 的账户"""
        return OKXAccount(initial_balance=10000.0)

    @pytest.fixture
    def engine(self):
        return MagicMock(spec=EventEngine)

    def create_filled_order(self, order_id, symbol, side, qty, price, fee=0.0):
        """辅助函数：创建一个已成交的订单"""
        # side: 1 for Buy, -1 for Sell. 
        # quantity should be positive, logic handles sign based on trade intent usually,
        # but here we follow Order class convention: 
        # usually quantity is positive, logic determines side.
        # But for cash flow calculation: cash_flow = -1 * qty * price.
        # So Buying (Long) -> qty > 0 -> cash_flow < 0 (Spend money)
        # Selling (Short) -> qty < 0 -> cash_flow > 0 (Receive money)
        
        real_qty = qty * side
        order = Order(
            order_id=order_id,
            order_type=OrderType.LIMIT_ORDER,
            symbol=symbol,
            quantity=real_qty, 
            price=price,
            state=OrderState.FILLED
        )
        order.filled_price = price
        order.commission_fee = fee
        # 手动触发 property 计算
        _ = order.quantity_int 
        return order

    def test_initial_state(self, account):
        assert account.get_balance() == 10000.0
        assert account.get_equity() == 10000.0
        assert len(account.get_positions()) == 0
        assert account.get_leverage() == 0

    def test_long_open_accounting(self, account):
        """测试：开多仓的会计核算 (Balance减少, Equity不变)"""
        symbol = "BTC-USDT-SWAP"
        entry_price = 50000.0
        qty = 1.0 # Buy 1 BTC
        fee = 5.0

        # 1. 模拟成交
        order = self.create_filled_order(1, symbol, 1, qty, entry_price, fee)
        account.on_order(order)
        # 更新市场价与成交价一致，以便观察初始权益
        account.price_dict[symbol] = entry_price

        # 2. 验证余额变化
        # Cash Flow = -1 * 1.0 * 50000 = -50000
        # Balance = 10000 - 50000 - 5 = -40005
        expected_balance = 10000.0 - 50000.0 - 5.0
        assert account.get_balance() == pytest.approx(expected_balance)

        # 3. 验证持仓
        positions = account.get_positions()
        assert positions[symbol] == pytest.approx(1.0)

        # 4. 验证权益 (Equity)
        # Equity = Balance + MarketValue
        # MarketValue = 1.0 * 50000 = 50000
        # Equity = -40005 + 50000 = 9995 (初始资金 - 手续费)
        assert account.get_equity() == pytest.approx(10000.0 - fee)
        
        # 验证杠杆率
        # Margin = 1.0 * 50000 = 50000
        # Leverage = 50000 / 9995 ≈ 5x
        assert account.get_leverage() == pytest.approx(50000 / 9995)

    def test_price_fluctuation_pnl(self, account):
        """测试：价格波动对浮动盈亏(Unrealized PnL)和权益的影响"""
        symbol = "BTC-USDT-SWAP"
        # 开仓 1 BTC @ 50000
        order = self.create_filled_order(1, symbol, 1, 1.0, 50000.0, 0.0)
        account.on_order(order)
        
        # 模拟市场价格上涨到 55000
        trade_event = OKXTrades(timestamp=100, symbol=symbol, trade_id=1, price=55000.0, size=0.1, side='buy')
        account.on_trade_data(trade_event)

        # 验证权益
        # Balance = 10000 - 50000 = -40000
        # Position Value = 1.0 * 55000 = 55000
        # Equity = -40000 + 55000 = 15000 (赚了5000)
        assert account.get_equity() == pytest.approx(15000.0)
        assert account.get_prices()[symbol] == 55000.0

    def test_funding_fee_deduction(self, account):
        """测试：资金费率扣除"""
        symbol = "BTC-USDT-SWAP"
        # 持有 1 BTC 多单
        order = self.create_filled_order(1, symbol, 1, 1.0, 50000.0, 0.0)
        account.on_order(order)

        # 收到资金费事件
        # 假设: 结算价(Mark Price) = 50000, 费率 = 0.0001 (0.01%)
        # 费用 = 1.0 * 50000 * 0.0001 = 5.0 USDT
        funding_event = OKXFundingRate(timestamp=200, symbol=symbol, funding_rate=0.0001, price=50000.0)
        account.on_funding_data(funding_event)

        # 验证余额减少
        # 初始操作后余额: 10000 - 50000 = -40000
        # 扣费后: -40000 - 5.0 = -40005
        assert account.get_balance() == pytest.approx(-40005.0)
        assert account.get_total_funding_fee() == pytest.approx(5.0)

    def test_short_selling_and_close(self, account):
        """测试：做空获利平仓"""
        symbol = "ETH-USDT-SWAP"
        
        # 1. 开空单 10 ETH @ 3000
        order_open = self.create_filled_order(101, symbol, -1, 10.0, 3000.0, 10.0)
        account.on_order(order_open)
        account.price_dict[symbol] = 3000.0

        # Cash Flow = -1 * (-10) * 3000 = +30000
        # Balance = 10000 + 30000 - 10 = 39990
        assert account.get_balance() == pytest.approx(39990.0)
        assert account.get_positions()[symbol] == pytest.approx(-10.0)
        
        # 2. 价格下跌到 2900 (做空盈利)
        account.price_dict[symbol] = 2900.0
        # Equity = Balance + PosVal
        # PosVal = -10 * 2900 = -29000
        # Equity = 39990 - 29000 = 10990 (盈利: (3000-2900)*10 - 10手续费 = 990)
        # 10000 + 990 = 10990. Correct.
        assert account.get_equity() == pytest.approx(10990.0)

        # 3. 平仓买入 10 ETH @ 2900
        order_close = self.create_filled_order(102, symbol, 1, 10.0, 2900.0, 10.0)
        account.on_order(order_close)

        # Cash Flow = -1 * 10 * 2900 = -29000
        # Balance = 39990 - 29000 - 10 = 10980
        # Position = 0
        assert account.get_balance() == pytest.approx(10980.0)
        assert symbol not in account.get_positions()
        
        # 验证总 PnL
        # 总利润 = 10980 - 10000 = 980
        # 交易毛利 = (3000 - 2900) * 10 = 1000
        # 手续费 = 10 + 10 = 20
        # 净利 = 980. Correct.
        assert account.get_equity() == pytest.approx(10980.0)

    def test_delivery_settlement(self, account):
        """测试：交割结算"""
        symbol = "BTC-USDT-SWAP"
        # 持有 1 BTC @ 50000
        order = self.create_filled_order(1, symbol, 1, 1.0, 50000.0, 0.0)
        account.on_order(order)
        
        # 收到交割事件，交割价 52000
        delivery_event = OKXDelivery(timestamp=300, symbol=symbol, price=52000.0)
        account.on_delivery_data(delivery_event)

        # 验证持仓已清空
        assert symbol not in account.get_positions()

        # 验证余额结算
        # 开仓后 Balance: 10000 - 50000 = -40000
        # 交割 CashFlow = Pos * DeliveryPrice = 1.0 * 52000 = 52000
        # 最终 Balance = -40000 + 52000 = 12000
        # 盈利 2000
        assert account.get_balance() == pytest.approx(12000.0)
        assert account.get_equity() == pytest.approx(12000.0)
        assert account.net_cash_flow[symbol] == pytest.approx(2000.0) # -50000 + 52000

    def test_metrics_calculation(self, account):
        """测试：成交量、手续费等统计指标"""
        symbol = "BTC-USDT-SWAP"
        # 交易 1: 买 1 @ 50000, Fee 5
        o1 = self.create_filled_order(1, symbol, 1, 1.0, 50000.0, 5.0)
        account.on_order(o1)
        
        # 交易 2: 卖 0.5 @ 51000, Fee 3
        o2 = self.create_filled_order(2, symbol, -1, 0.5, 51000.0, 3.0)
        account.on_order(o2)

        # 验证统计
        # Turnover: 50000*1 + 51000*0.5 = 75500
        assert account.get_total_turnover() == pytest.approx(75500.0)
        # Commission: 5 + 3 = 8
        assert account.get_total_commission() == pytest.approx(8.0)
        # Count: 2
        assert account.get_total_trade_count() == 2
        
        # 验证 Total Trade PnL
        # Cash Flow 1: -50000
        # Cash Flow 2: +25500
        # Net Cash Flow: -24500
        # Remaining Pos: 0.5
        # Current Price (from last order fill implicitly or set explicitly): 51000
        account.price_dict[symbol] = 51000.0
        # Pos Value: 0.5 * 51000 = 25500
        # Total Trade PnL = -24500 + 25500 = 1000
        # Manual Calc:
        # Trade 1: Buy 1 @ 50000.
        # Trade 2: Sell 0.5 @ 51000 -> Profit (51000-50000)*0.5 = 500.
        # Remaining: 0.5 @ 50000, Current 51000 -> Unrealized (51000-50000)*0.5 = 500.
        # Total = 1000. Correct.
        assert account.get_total_trade_pnl() == pytest.approx(1000.0)


if __name__ == "__main__":
    # 方式 A: 调用 pytest 运行当前文件 (推荐)
    # -v: 显示详细信息
    # -s: 允许在控制台显示 print 输出 (便于调试)
    import sys
    sys.exit(pytest.main(["-v", "-s", __file__]))

    # 方式 B: 如果您想手动单步调试某个特定方法，不走 pytest 流程
    # 您需要手动创建 account 对象传进去，如下所示：
    """
    # 1. 手动创建测试类实例
    tester = TestOKXAccount()
    
    # 2. 手动创建依赖对象 (模拟 fixture)
    debug_account = OKXAccount(initial_balance=10000.0)
    
    # 3. 调用您想 Debug 的具体测试方法，并传入依赖
    print("Start debugging test_long_open_accounting...")
    tester.test_long_open_accounting(debug_account)
    print("Test passed!")
    """