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


class OKXTrades(Event):
    """
    标准扁平数据类定义
    1. 继承Event类而非Data，弃用Data类
    2. 使用__slots__定义字段，但不要包含父类的字段
    3. 在__init__中定义字段的初始化
    """
    
    __slots__ = (
        "instrument_name",
        "trade_id",
        "price",
        "size",
        "side",
    )
    def __init__(
        self,
        timestamp: int,
        instrument_name: str,
        trade_id: str,
        price: float,
        size: float,
        side: str,
    ):
        super().__init__(timestamp)
        self.instrument_name = instrument_name
        self.trade_id = trade_id
        self.price = price
        self.size = size
        self.side = side

    # def __repr__(self) -> str:
    #     return (f"OKXTrades(timestamp={self.timestamp}, instrument_name={self.instrument_name}, "
    #             f"trade_id={self.trade_id}, price={self.price}, size={self.size}, side={self.side})")

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