from hft_backtest import Event

"""
基于数据定义 OKX 相关Data类型 (显式展开定义版)
"""

class OKXBookticker(Event):
    """
    来自 OKX 的 OrderBook 数据 (25档)
    显式定义所有字段以支持 IDE 提示和静态检查。
    """
    __slots__ = (
        "exchange", "symbol", "local_timestamp",
        # Depth 1
        "ask_price_1", "ask_amount_1", "bid_price_1", "bid_amount_1",
        # Depth 2
        "ask_price_2", "ask_amount_2", "bid_price_2", "bid_amount_2",
        # Depth 3
        "ask_price_3", "ask_amount_3", "bid_price_3", "bid_amount_3",
        # Depth 4
        "ask_price_4", "ask_amount_4", "bid_price_4", "bid_amount_4",
        # Depth 5
        "ask_price_5", "ask_amount_5", "bid_price_5", "bid_amount_5",
        # Depth 6
        "ask_price_6", "ask_amount_6", "bid_price_6", "bid_amount_6",
        # Depth 7
        "ask_price_7", "ask_amount_7", "bid_price_7", "bid_amount_7",
        # Depth 8
        "ask_price_8", "ask_amount_8", "bid_price_8", "bid_amount_8",
        # Depth 9
        "ask_price_9", "ask_amount_9", "bid_price_9", "bid_amount_9",
        # Depth 10
        "ask_price_10", "ask_amount_10", "bid_price_10", "bid_amount_10",
        # Depth 11
        "ask_price_11", "ask_amount_11", "bid_price_11", "bid_amount_11",
        # Depth 12
        "ask_price_12", "ask_amount_12", "bid_price_12", "bid_amount_12",
        # Depth 13
        "ask_price_13", "ask_amount_13", "bid_price_13", "bid_amount_13",
        # Depth 14
        "ask_price_14", "ask_amount_14", "bid_price_14", "bid_amount_14",
        # Depth 15
        "ask_price_15", "ask_amount_15", "bid_price_15", "bid_amount_15",
        # Depth 16
        "ask_price_16", "ask_amount_16", "bid_price_16", "bid_amount_16",
        # Depth 17
        "ask_price_17", "ask_amount_17", "bid_price_17", "bid_amount_17",
        # Depth 18
        "ask_price_18", "ask_amount_18", "bid_price_18", "bid_amount_18",
        # Depth 19
        "ask_price_19", "ask_amount_19", "bid_price_19", "bid_amount_19",
        # Depth 20
        "ask_price_20", "ask_amount_20", "bid_price_20", "bid_amount_20",
        # Depth 21
        "ask_price_21", "ask_amount_21", "bid_price_21", "bid_amount_21",
        # Depth 22
        "ask_price_22", "ask_amount_22", "bid_price_22", "bid_amount_22",
        # Depth 23
        "ask_price_23", "ask_amount_23", "bid_price_23", "bid_amount_23",
        # Depth 24
        "ask_price_24", "ask_amount_24", "bid_price_24", "bid_amount_24",
        # Depth 25
        "ask_price_25", "ask_amount_25", "bid_price_25", "bid_amount_25",
    )

    def __init__(
        self, 
        timestamp: int = 0, 
        exchange: str = "", 
        symbol: str = "", 
        local_timestamp: int = 0,
        # Depth 1
        ask_price_1: float = 0.0, ask_amount_1: float = 0.0, bid_price_1: float = 0.0, bid_amount_1: float = 0.0,
        # Depth 2
        ask_price_2: float = 0.0, ask_amount_2: float = 0.0, bid_price_2: float = 0.0, bid_amount_2: float = 0.0,
        # Depth 3
        ask_price_3: float = 0.0, ask_amount_3: float = 0.0, bid_price_3: float = 0.0, bid_amount_3: float = 0.0,
        # Depth 4
        ask_price_4: float = 0.0, ask_amount_4: float = 0.0, bid_price_4: float = 0.0, bid_amount_4: float = 0.0,
        # Depth 5
        ask_price_5: float = 0.0, ask_amount_5: float = 0.0, bid_price_5: float = 0.0, bid_amount_5: float = 0.0,
        # Depth 6
        ask_price_6: float = 0.0, ask_amount_6: float = 0.0, bid_price_6: float = 0.0, bid_amount_6: float = 0.0,
        # Depth 7
        ask_price_7: float = 0.0, ask_amount_7: float = 0.0, bid_price_7: float = 0.0, bid_amount_7: float = 0.0,
        # Depth 8
        ask_price_8: float = 0.0, ask_amount_8: float = 0.0, bid_price_8: float = 0.0, bid_amount_8: float = 0.0,
        # Depth 9
        ask_price_9: float = 0.0, ask_amount_9: float = 0.0, bid_price_9: float = 0.0, bid_amount_9: float = 0.0,
        # Depth 10
        ask_price_10: float = 0.0, ask_amount_10: float = 0.0, bid_price_10: float = 0.0, bid_amount_10: float = 0.0,
        # Depth 11
        ask_price_11: float = 0.0, ask_amount_11: float = 0.0, bid_price_11: float = 0.0, bid_amount_11: float = 0.0,
        # Depth 12
        ask_price_12: float = 0.0, ask_amount_12: float = 0.0, bid_price_12: float = 0.0, bid_amount_12: float = 0.0,
        # Depth 13
        ask_price_13: float = 0.0, ask_amount_13: float = 0.0, bid_price_13: float = 0.0, bid_amount_13: float = 0.0,
        # Depth 14
        ask_price_14: float = 0.0, ask_amount_14: float = 0.0, bid_price_14: float = 0.0, bid_amount_14: float = 0.0,
        # Depth 15
        ask_price_15: float = 0.0, ask_amount_15: float = 0.0, bid_price_15: float = 0.0, bid_amount_15: float = 0.0,
        # Depth 16
        ask_price_16: float = 0.0, ask_amount_16: float = 0.0, bid_price_16: float = 0.0, bid_amount_16: float = 0.0,
        # Depth 17
        ask_price_17: float = 0.0, ask_amount_17: float = 0.0, bid_price_17: float = 0.0, bid_amount_17: float = 0.0,
        # Depth 18
        ask_price_18: float = 0.0, ask_amount_18: float = 0.0, bid_price_18: float = 0.0, bid_amount_18: float = 0.0,
        # Depth 19
        ask_price_19: float = 0.0, ask_amount_19: float = 0.0, bid_price_19: float = 0.0, bid_amount_19: float = 0.0,
        # Depth 20
        ask_price_20: float = 0.0, ask_amount_20: float = 0.0, bid_price_20: float = 0.0, bid_amount_20: float = 0.0,
        # Depth 21
        ask_price_21: float = 0.0, ask_amount_21: float = 0.0, bid_price_21: float = 0.0, bid_amount_21: float = 0.0,
        # Depth 22
        ask_price_22: float = 0.0, ask_amount_22: float = 0.0, bid_price_22: float = 0.0, bid_amount_22: float = 0.0,
        # Depth 23
        ask_price_23: float = 0.0, ask_amount_23: float = 0.0, bid_price_23: float = 0.0, bid_amount_23: float = 0.0,
        # Depth 24
        ask_price_24: float = 0.0, ask_amount_24: float = 0.0, bid_price_24: float = 0.0, bid_amount_24: float = 0.0,
        # Depth 25
        ask_price_25: float = 0.0, ask_amount_25: float = 0.0, bid_price_25: float = 0.0, bid_amount_25: float = 0.0,
    ):
        super().__init__(timestamp)
        self.source = 0
        self.producer = 0
        self.exchange = exchange
        self.symbol = symbol
        self.local_timestamp = local_timestamp
        
        # Depth 1
        self.ask_price_1 = ask_price_1; self.ask_amount_1 = ask_amount_1; self.bid_price_1 = bid_price_1; self.bid_amount_1 = bid_amount_1
        # Depth 2
        self.ask_price_2 = ask_price_2; self.ask_amount_2 = ask_amount_2; self.bid_price_2 = bid_price_2; self.bid_amount_2 = bid_amount_2
        # Depth 3
        self.ask_price_3 = ask_price_3; self.ask_amount_3 = ask_amount_3; self.bid_price_3 = bid_price_3; self.bid_amount_3 = bid_amount_3
        # Depth 4
        self.ask_price_4 = ask_price_4; self.ask_amount_4 = ask_amount_4; self.bid_price_4 = bid_price_4; self.bid_amount_4 = bid_amount_4
        # Depth 5
        self.ask_price_5 = ask_price_5; self.ask_amount_5 = ask_amount_5; self.bid_price_5 = bid_price_5; self.bid_amount_5 = bid_amount_5
        # Depth 6
        self.ask_price_6 = ask_price_6; self.ask_amount_6 = ask_amount_6; self.bid_price_6 = bid_price_6; self.bid_amount_6 = bid_amount_6
        # Depth 7
        self.ask_price_7 = ask_price_7; self.ask_amount_7 = ask_amount_7; self.bid_price_7 = bid_price_7; self.bid_amount_7 = bid_amount_7
        # Depth 8
        self.ask_price_8 = ask_price_8; self.ask_amount_8 = ask_amount_8; self.bid_price_8 = bid_price_8; self.bid_amount_8 = bid_amount_8
        # Depth 9
        self.ask_price_9 = ask_price_9; self.ask_amount_9 = ask_amount_9; self.bid_price_9 = bid_price_9; self.bid_amount_9 = bid_amount_9
        # Depth 10
        self.ask_price_10 = ask_price_10; self.ask_amount_10 = ask_amount_10; self.bid_price_10 = bid_price_10; self.bid_amount_10 = bid_amount_10
        # Depth 11
        self.ask_price_11 = ask_price_11; self.ask_amount_11 = ask_amount_11; self.bid_price_11 = bid_price_11; self.bid_amount_11 = bid_amount_11
        # Depth 12
        self.ask_price_12 = ask_price_12; self.ask_amount_12 = ask_amount_12; self.bid_price_12 = bid_price_12; self.bid_amount_12 = bid_amount_12
        # Depth 13
        self.ask_price_13 = ask_price_13; self.ask_amount_13 = ask_amount_13; self.bid_price_13 = bid_price_13; self.bid_amount_13 = bid_amount_13
        # Depth 14
        self.ask_price_14 = ask_price_14; self.ask_amount_14 = ask_amount_14; self.bid_price_14 = bid_price_14; self.bid_amount_14 = bid_amount_14
        # Depth 15
        self.ask_price_15 = ask_price_15; self.ask_amount_15 = ask_amount_15; self.bid_price_15 = bid_price_15; self.bid_amount_15 = bid_amount_15
        # Depth 16
        self.ask_price_16 = ask_price_16; self.ask_amount_16 = ask_amount_16; self.bid_price_16 = bid_price_16; self.bid_amount_16 = bid_amount_16
        # Depth 17
        self.ask_price_17 = ask_price_17; self.ask_amount_17 = ask_amount_17; self.bid_price_17 = bid_price_17; self.bid_amount_17 = bid_amount_17
        # Depth 18
        self.ask_price_18 = ask_price_18; self.ask_amount_18 = ask_amount_18; self.bid_price_18 = bid_price_18; self.bid_amount_18 = bid_amount_18
        # Depth 19
        self.ask_price_19 = ask_price_19; self.ask_amount_19 = ask_amount_19; self.bid_price_19 = bid_price_19; self.bid_amount_19 = bid_amount_19
        # Depth 20
        self.ask_price_20 = ask_price_20; self.ask_amount_20 = ask_amount_20; self.bid_price_20 = bid_price_20; self.bid_amount_20 = bid_amount_20
        # Depth 21
        self.ask_price_21 = ask_price_21; self.ask_amount_21 = ask_amount_21; self.bid_price_21 = bid_price_21; self.bid_amount_21 = bid_amount_21
        # Depth 22
        self.ask_price_22 = ask_price_22; self.ask_amount_22 = ask_amount_22; self.bid_price_22 = bid_price_22; self.bid_amount_22 = bid_amount_22
        # Depth 23
        self.ask_price_23 = ask_price_23; self.ask_amount_23 = ask_amount_23; self.bid_price_23 = bid_price_23; self.bid_amount_23 = bid_amount_23
        # Depth 24
        self.ask_price_24 = ask_price_24; self.ask_amount_24 = ask_amount_24; self.bid_price_24 = bid_price_24; self.bid_amount_24 = bid_amount_24
        # Depth 25
        self.ask_price_25 = ask_price_25; self.ask_amount_25 = ask_amount_25; self.bid_price_25 = bid_price_25; self.bid_amount_25 = bid_amount_25


class OKXTrades(Event):
    __slots__ = (
        "symbol",
        "trade_id",
        "price",
        "size",
        "side",
    )
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        trade_id: str = "",
        price: float = 0.0,
        size: float = 0.0,
        side: str = "",
    ):
        super().__init__(timestamp)
        self.symbol = symbol
        self.trade_id = trade_id
        self.price = price
        self.size = size
        self.side = side

    def __repr__(self) -> str:
        return (f"OKXTrades(timestamp={self.timestamp}, symbol={self.symbol}, "
                f"trade_id={self.trade_id}, price={self.price}, size={self.size}, side={self.side})")

class OKXFundingRate(Event):
    __slots__ = (
        "symbol",
        "funding_rate",
        "price"
    )
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        funding_rate: float = 0.0,
        price: float = 0.0,
    ):
        super().__init__(timestamp)
        self.symbol = symbol
        self.funding_rate = funding_rate
        self.price = price

class OKXDelivery(Event):
    __slots__ = (
        "symbol",
        "price",
    )
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        price: float = 0.0,
    ):
        super().__init__(timestamp)
        self.symbol = symbol
        self.price = price

class OKXPremium(Event):
    __slots__ = (
        "symbol",
        "premium",
    )
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        premium: float = 0.0,
    ):
        super().__init__(timestamp)
        self.symbol = symbol
        self.premium = premium