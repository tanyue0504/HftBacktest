from hft_backtest import Event, EventEngine, Order, Data

"""
基于数据定义 OKX 相关Data类型

OKXBooktickerData
来自 OKX 的OrderBook数据
包含字段：
- timestamp: 数据时间戳 (int)
- symbol: 交易对名称 (str)
- bids/asks_price/amount_1~25: 50档买卖盘价格和数量

OKXTradesData
来自 OKX 的逐笔成交数据
包含字段：
- created_time: 数据时间戳 (int)
- symbol: 交易对名称 (str)
- trade_id: 成交ID (str)
- price: 成交价格 (float)
- size: 成交数量 (float)
- side: 成交方向 (str)，buy/sell

OKXFundingRateData
来自 OKX 的资金费率数据
包含字段：
- timestamp: 数据时间戳 (int)
- symbol: 交易对名称 (str)
- funding_rate: 资金费率 (float)
- price: 标记价格 (float), 计算资金费的依据

OKXDeliveryData
来自 OKX 的交割/强平数据
包含字段：
- timestamp: 数据时间戳 (int)
- symbol: 交易对名称 (str)
- price: 交割/强平价格 (float)
"""
class OKXBookticker(Data):
    def __init__(
        self,
        timestamp: int,
        name: str,
        data,
    ):
        super().__init__(timestamp, name, data)

class OKXTrades(Data):
    def __init__(
        self,
        timestamp: int,
        name: str,
        data,
    ):
        super().__init__(timestamp, name, data)

class OKXFundingRate(Data):
    def __init__(
        self,
        timestamp: int,
        name: str,
        data,
    ):
        super().__init__(timestamp, name, data)

class OKXDelivery(Data):
    def __init__(
        self,
        timestamp: int,
        name: str,
        data,
    ):
        super().__init__(timestamp, name, data)