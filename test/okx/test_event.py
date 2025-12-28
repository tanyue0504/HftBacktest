import pytest
from hft_backtest.okx.event import OKXBookticker, OKXTrades, OKXFundingRate
from hft_backtest.order import Order

class TestOKXEvents:
    def test_bookticker_layout_and_derive(self):
        """
        测试 OKXBookticker 的内存布局和克隆机制
        重点验证：Event.derive 能否正确拷贝子类定义的巨量 C 字段
        """
        # 1. 创建一个包含数据的 Ticker
        ticker = OKXBookticker(timestamp=1000, symbol="BTC-USDT")
        
        # 填充一些特定档位的数据
        ticker.ask_price_1 = 50001.0
        ticker.ask_amount_1 = 1.5
        ticker.bid_price_25 = 49000.0
        ticker.bid_amount_25 = 10.0
        
        # 2. 克隆
        clone = ticker.derive()
        
        # 3. 验证基础字段
        assert clone.timestamp == 0  # derive 会重置 timestamp
        assert clone.symbol == "BTC-USDT"
        assert isinstance(clone, OKXBookticker)
        
        # 4. 验证扩展字段 (C double) 是否被 memcpy 过来
        assert clone.ask_price_1 == 50001.0
        assert clone.ask_amount_1 == 1.5
        assert clone.bid_price_25 == 49000.0
        assert clone.bid_amount_25 == 10.0
        
        # 5. 验证独立性 (修改副本不影响原件)
        clone.ask_price_1 = 99999.0
        assert ticker.ask_price_1 == 50001.0

    def test_trades_derive(self):
        """测试 OKXTrades 的克隆"""
        trade = OKXTrades(timestamp=123, symbol="ETH-USDT", trade_id=88888888, price=2000.0, size=0.1, side="buy")
        
        clone = trade.derive()
        
        assert clone.trade_id == 88888888
        assert clone.price == 2000.0
        assert clone.side == "buy"
        assert clone.symbol == "ETH-USDT"
        
        # 验证 C 字符串引用的安全性
        # (Event.derive 应该对 str 进行了 INCREF，这里通过修改检查独立性，虽然 str 是不可变的)
        clone.symbol = "SOL-USDT"
        assert trade.symbol == "ETH-USDT"

    def test_funding_rate(self):
        """简单测试其他类型的初始化"""
        fr = OKXFundingRate(timestamp=100, symbol="BTC-USDT", funding_rate=0.0001, price=30000)
        assert fr.funding_rate == 0.0001
        
        clone = fr.derive()
        assert clone.funding_rate == 0.0001

if __name__ == "__main__":
    pytest.main(["-v", __file__])