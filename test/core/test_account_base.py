import pytest
import sys
from hft_backtest.account import Account
from hft_backtest.order import Order
from hft_backtest.event_engine import EventEngine

class TestAccountBase:
    def test_abstract_enforcement(self):
        """测试基类强制要求子类实现接口"""
        acc = Account()
        o = Order.create_limit("BTC", 1, 100)
        
        # 调用任何未实现的方法都应该抛出 NotImplementedError
        with pytest.raises(NotImplementedError, match="on_order"):
            acc.on_order(o)
            
        with pytest.raises(NotImplementedError, match="get_balance"):
            acc.get_balance()
            
        with pytest.raises(NotImplementedError, match="get_total_turnover"):
            acc.get_total_turnover()

    def test_concrete_subclass(self):
        """测试一个最小化的具体实现"""
        class MinimalAccount(Account):
            def __init__(self):
                self.balance = 100.0
                
            # 实现所有必需接口
            def on_order(self, order): pass
            def get_positions(self): return {}
            def get_orders(self): return {}
            def get_prices(self): return {}
            def get_balance(self): return self.balance
            def get_equity(self): return self.balance
            
            def get_total_turnover(self): return 0.0
            def get_total_commission(self): return 0.0
            def get_total_funding_fee(self): return 0.0
            def get_total_trade_pnl(self): return 0.0
            def get_total_trade_count(self): return 0

        acc = MinimalAccount()
        assert acc.get_balance() == 100.0
        # 调用不报错
        acc.get_total_turnover()

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))