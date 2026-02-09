from hft_backtest import Event

class BarEvent(Event):
    """
    Bar事件
    timestamp必须用close_time否则与框架字段含义不匹配
    包含：开盘价、最高价、最低价、收盘价、成交量、下一个周期的开盘价（可选）
    """
    def __init__(self, timestamp, open_price, high_price, low_price, close_price, volume, next_open_price=None):
        self.super().__init__(timestamp)
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.next_open_price = next_open_price

class DeliveryEvent(Event):
    """
    Event triggered for delivery of assets or settlements.
    """
    def __init__(self, timestamp, asset, quantity, price):
        self.super().__init__(timestamp)
        self.asset = asset
        self.quantity = quantity
        self.price = price