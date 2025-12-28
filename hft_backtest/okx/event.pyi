from hft_backtest.event import Event

class OKXBookticker(Event):
    symbol: str
    local_timestamp: int
    
    # Depth 1
    ask_price_1: float
    ask_amount_1: float
    bid_price_1: float
    bid_amount_1: float
    
    # Depth 2
    ask_price_2: float
    ask_amount_2: float
    bid_price_2: float
    bid_amount_2: float
    
    # Depth 3
    ask_price_3: float
    ask_amount_3: float
    bid_price_3: float
    bid_amount_3: float
    
    # Depth 4
    ask_price_4: float
    ask_amount_4: float
    bid_price_4: float
    bid_amount_4: float
    
    # Depth 5
    ask_price_5: float
    ask_amount_5: float
    bid_price_5: float
    bid_amount_5: float
    
    # Depth 6
    ask_price_6: float
    ask_amount_6: float
    bid_price_6: float
    bid_amount_6: float
    
    # Depth 7
    ask_price_7: float
    ask_amount_7: float
    bid_price_7: float
    bid_amount_7: float
    
    # Depth 8
    ask_price_8: float
    ask_amount_8: float
    bid_price_8: float
    bid_amount_8: float
    
    # Depth 9
    ask_price_9: float
    ask_amount_9: float
    bid_price_9: float
    bid_amount_9: float
    
    # Depth 10
    ask_price_10: float
    ask_amount_10: float
    bid_price_10: float
    bid_amount_10: float
    
    # Depth 11
    ask_price_11: float
    ask_amount_11: float
    bid_price_11: float
    bid_amount_11: float
    
    # Depth 12
    ask_price_12: float
    ask_amount_12: float
    bid_price_12: float
    bid_amount_12: float
    
    # Depth 13
    ask_price_13: float
    ask_amount_13: float
    bid_price_13: float
    bid_amount_13: float
    
    # Depth 14
    ask_price_14: float
    ask_amount_14: float
    bid_price_14: float
    bid_amount_14: float
    
    # Depth 15
    ask_price_15: float
    ask_amount_15: float
    bid_price_15: float
    bid_amount_15: float
    
    # Depth 16
    ask_price_16: float
    ask_amount_16: float
    bid_price_16: float
    bid_amount_16: float
    
    # Depth 17
    ask_price_17: float
    ask_amount_17: float
    bid_price_17: float
    bid_amount_17: float
    
    # Depth 18
    ask_price_18: float
    ask_amount_18: float
    bid_price_18: float
    bid_amount_18: float
    
    # Depth 19
    ask_price_19: float
    ask_amount_19: float
    bid_price_19: float
    bid_amount_19: float
    
    # Depth 20
    ask_price_20: float
    ask_amount_20: float
    bid_price_20: float
    bid_amount_20: float
    
    # Depth 21
    ask_price_21: float
    ask_amount_21: float
    bid_price_21: float
    bid_amount_21: float
    
    # Depth 22
    ask_price_22: float
    ask_amount_22: float
    bid_price_22: float
    bid_amount_22: float
    
    # Depth 23
    ask_price_23: float
    ask_amount_23: float
    bid_price_23: float
    bid_amount_23: float
    
    # Depth 24
    ask_price_24: float
    ask_amount_24: float
    bid_price_24: float
    bid_amount_24: float
    
    # Depth 25
    ask_price_25: float
    ask_amount_25: float
    bid_price_25: float
    bid_amount_25: float

    def __init__(
        self, 
        timestamp: int = 0, 
        symbol: str = "", 
        local_timestamp: int = 0,
        ask_price_1: float = 0.0, ask_amount_1: float = 0.0, bid_price_1: float = 0.0, bid_amount_1: float = 0.0,
        ask_price_2: float = 0.0, ask_amount_2: float = 0.0, bid_price_2: float = 0.0, bid_amount_2: float = 0.0,
        ask_price_3: float = 0.0, ask_amount_3: float = 0.0, bid_price_3: float = 0.0, bid_amount_3: float = 0.0,
        ask_price_4: float = 0.0, ask_amount_4: float = 0.0, bid_price_4: float = 0.0, bid_amount_4: float = 0.0,
        ask_price_5: float = 0.0, ask_amount_5: float = 0.0, bid_price_5: float = 0.0, bid_amount_5: float = 0.0,
        ask_price_6: float = 0.0, ask_amount_6: float = 0.0, bid_price_6: float = 0.0, bid_amount_6: float = 0.0,
        ask_price_7: float = 0.0, ask_amount_7: float = 0.0, bid_price_7: float = 0.0, bid_amount_7: float = 0.0,
        ask_price_8: float = 0.0, ask_amount_8: float = 0.0, bid_price_8: float = 0.0, bid_amount_8: float = 0.0,
        ask_price_9: float = 0.0, ask_amount_9: float = 0.0, bid_price_9: float = 0.0, bid_amount_9: float = 0.0,
        ask_price_10: float = 0.0, ask_amount_10: float = 0.0, bid_price_10: float = 0.0, bid_amount_10: float = 0.0,
        ask_price_11: float = 0.0, ask_amount_11: float = 0.0, bid_price_11: float = 0.0, bid_amount_11: float = 0.0,
        ask_price_12: float = 0.0, ask_amount_12: float = 0.0, bid_price_12: float = 0.0, bid_amount_12: float = 0.0,
        ask_price_13: float = 0.0, ask_amount_13: float = 0.0, bid_price_13: float = 0.0, bid_amount_13: float = 0.0,
        ask_price_14: float = 0.0, ask_amount_14: float = 0.0, bid_price_14: float = 0.0, bid_amount_14: float = 0.0,
        ask_price_15: float = 0.0, ask_amount_15: float = 0.0, bid_price_15: float = 0.0, bid_amount_15: float = 0.0,
        ask_price_16: float = 0.0, ask_amount_16: float = 0.0, bid_price_16: float = 0.0, bid_amount_16: float = 0.0,
        ask_price_17: float = 0.0, ask_amount_17: float = 0.0, bid_price_17: float = 0.0, bid_amount_17: float = 0.0,
        ask_price_18: float = 0.0, ask_amount_18: float = 0.0, bid_price_18: float = 0.0, bid_amount_18: float = 0.0,
        ask_price_19: float = 0.0, ask_amount_19: float = 0.0, bid_price_19: float = 0.0, bid_amount_19: float = 0.0,
        ask_price_20: float = 0.0, ask_amount_20: float = 0.0, bid_price_20: float = 0.0, bid_amount_20: float = 0.0,
        ask_price_21: float = 0.0, ask_amount_21: float = 0.0, bid_price_21: float = 0.0, bid_amount_21: float = 0.0,
        ask_price_22: float = 0.0, ask_amount_22: float = 0.0, bid_price_22: float = 0.0, bid_amount_22: float = 0.0,
        ask_price_23: float = 0.0, ask_amount_23: float = 0.0, bid_price_23: float = 0.0, bid_amount_23: float = 0.0,
        ask_price_24: float = 0.0, ask_amount_24: float = 0.0, bid_price_24: float = 0.0, bid_amount_24: float = 0.0,
        ask_price_25: float = 0.0, ask_amount_25: float = 0.0, bid_price_25: float = 0.0, bid_amount_25: float = 0.0,
    ) -> None: ...

class OKXTrades(Event):
    symbol: str
    trade_id: int
    price: float
    size: float
    side: str
    
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        trade_id: int = 0,
        price: float = 0.0,
        size: float = 0.0,
        side: str = "",
    ) -> None: ...

class OKXFundingRate(Event):
    symbol: str
    funding_rate: float
    price: float
    
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        funding_rate: float = 0.0,
        price: float = 0.0,
    ) -> None: ...

class OKXDelivery(Event):
    symbol: str
    price: float
    
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        price: float = 0.0,
    ) -> None: ...

class OKXPremium(Event):
    symbol: str
    premium: float
    
    def __init__(
        self,
        timestamp: int = 0,
        symbol: str = "",
        premium: float = 0.0,
    ) -> None: ...