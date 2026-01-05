# hft_backtest/okx/event.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.event cimport Event

# =============================================================================
# OKXBookticker (已优化)
# =============================================================================
cdef class OKXBookticker(Event):
    def __init__(
        self, 
        long long timestamp = 0,  
        str symbol = "", 
        long long local_timestamp = 0,
        double ask_price_1 = 0.0, double ask_amount_1 = 0.0, double bid_price_1 = 0.0, double bid_amount_1 = 0.0,
        double ask_price_2 = 0.0, double ask_amount_2 = 0.0, double bid_price_2 = 0.0, double bid_amount_2 = 0.0,
        double ask_price_3 = 0.0, double ask_amount_3 = 0.0, double bid_price_3 = 0.0, double bid_amount_3 = 0.0,
        double ask_price_4 = 0.0, double ask_amount_4 = 0.0, double bid_price_4 = 0.0, double bid_amount_4 = 0.0,
        double ask_price_5 = 0.0, double ask_amount_5 = 0.0, double bid_price_5 = 0.0, double bid_amount_5 = 0.0,
        double ask_price_6 = 0.0, double ask_amount_6 = 0.0, double bid_price_6 = 0.0, double bid_amount_6 = 0.0,
        double ask_price_7 = 0.0, double ask_amount_7 = 0.0, double bid_price_7 = 0.0, double bid_amount_7 = 0.0,
        double ask_price_8 = 0.0, double ask_amount_8 = 0.0, double bid_price_8 = 0.0, double bid_amount_8 = 0.0,
        double ask_price_9 = 0.0, double ask_amount_9 = 0.0, double bid_price_9 = 0.0, double bid_amount_9 = 0.0,
        double ask_price_10 = 0.0, double ask_amount_10 = 0.0, double bid_price_10 = 0.0, double bid_amount_10 = 0.0,
        double ask_price_11 = 0.0, double ask_amount_11 = 0.0, double bid_price_11 = 0.0, double bid_amount_11 = 0.0,
        double ask_price_12 = 0.0, double ask_amount_12 = 0.0, double bid_price_12 = 0.0, double bid_amount_12 = 0.0,
        double ask_price_13 = 0.0, double ask_amount_13 = 0.0, double bid_price_13 = 0.0, double bid_amount_13 = 0.0,
        double ask_price_14 = 0.0, double ask_amount_14 = 0.0, double bid_price_14 = 0.0, double bid_amount_14 = 0.0,
        double ask_price_15 = 0.0, double ask_amount_15 = 0.0, double bid_price_15 = 0.0, double bid_amount_15 = 0.0,
        double ask_price_16 = 0.0, double ask_amount_16 = 0.0, double bid_price_16 = 0.0, double bid_amount_16 = 0.0,
        double ask_price_17 = 0.0, double ask_amount_17 = 0.0, double bid_price_17 = 0.0, double bid_amount_17 = 0.0,
        double ask_price_18 = 0.0, double ask_amount_18 = 0.0, double bid_price_18 = 0.0, double bid_amount_18 = 0.0,
        double ask_price_19 = 0.0, double ask_amount_19 = 0.0, double bid_price_19 = 0.0, double bid_amount_19 = 0.0,
        double ask_price_20 = 0.0, double ask_amount_20 = 0.0, double bid_price_20 = 0.0, double bid_amount_20 = 0.0,
        double ask_price_21 = 0.0, double ask_amount_21 = 0.0, double bid_price_21 = 0.0, double bid_amount_21 = 0.0,
        double ask_price_22 = 0.0, double ask_amount_22 = 0.0, double bid_price_22 = 0.0, double bid_amount_22 = 0.0,
        double ask_price_23 = 0.0, double ask_amount_23 = 0.0, double bid_price_23 = 0.0, double bid_amount_23 = 0.0,
        double ask_price_24 = 0.0, double ask_amount_24 = 0.0, double bid_price_24 = 0.0, double bid_amount_24 = 0.0,
        double ask_price_25 = 0.0, double ask_amount_25 = 0.0, double bid_price_25 = 0.0, double bid_amount_25 = 0.0,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.local_timestamp = local_timestamp
        
        self.ask_price_1 = ask_price_1; self.ask_amount_1 = ask_amount_1; self.bid_price_1 = bid_price_1; self.bid_amount_1 = bid_amount_1
        self.ask_price_2 = ask_price_2; self.ask_amount_2 = ask_amount_2; self.bid_price_2 = bid_price_2; self.bid_amount_2 = bid_amount_2
        self.ask_price_3 = ask_price_3; self.ask_amount_3 = ask_amount_3; self.bid_price_3 = bid_price_3; self.bid_amount_3 = bid_amount_3
        self.ask_price_4 = ask_price_4; self.ask_amount_4 = ask_amount_4; self.bid_price_4 = bid_price_4; self.bid_amount_4 = bid_amount_4
        self.ask_price_5 = ask_price_5; self.ask_amount_5 = ask_amount_5; self.bid_price_5 = bid_price_5; self.bid_amount_5 = bid_amount_5
        self.ask_price_6 = ask_price_6; self.ask_amount_6 = ask_amount_6; self.bid_price_6 = bid_price_6; self.bid_amount_6 = bid_amount_6
        self.ask_price_7 = ask_price_7; self.ask_amount_7 = ask_amount_7; self.bid_price_7 = bid_price_7; self.bid_amount_7 = bid_amount_7
        self.ask_price_8 = ask_price_8; self.ask_amount_8 = ask_amount_8; self.bid_price_8 = bid_price_8; self.bid_amount_8 = bid_amount_8
        self.ask_price_9 = ask_price_9; self.ask_amount_9 = ask_amount_9; self.bid_price_9 = bid_price_9; self.bid_amount_9 = bid_amount_9
        self.ask_price_10 = ask_price_10; self.ask_amount_10 = ask_amount_10; self.bid_price_10 = bid_price_10; self.bid_amount_10 = bid_amount_10
        self.ask_price_11 = ask_price_11; self.ask_amount_11 = ask_amount_11; self.bid_price_11 = bid_price_11; self.bid_amount_11 = bid_amount_11
        self.ask_price_12 = ask_price_12; self.ask_amount_12 = ask_amount_12; self.bid_price_12 = bid_price_12; self.bid_amount_12 = bid_amount_12
        self.ask_price_13 = ask_price_13; self.ask_amount_13 = ask_amount_13; self.bid_price_13 = bid_price_13; self.bid_amount_13 = bid_amount_13
        self.ask_price_14 = ask_price_14; self.ask_amount_14 = ask_amount_14; self.bid_price_14 = bid_price_14; self.bid_amount_14 = bid_amount_14
        self.ask_price_15 = ask_price_15; self.ask_amount_15 = ask_amount_15; self.bid_price_15 = bid_price_15; self.bid_amount_15 = bid_amount_15
        self.ask_price_16 = ask_price_16; self.ask_amount_16 = ask_amount_16; self.bid_price_16 = bid_price_16; self.bid_amount_16 = bid_amount_16
        self.ask_price_17 = ask_price_17; self.ask_amount_17 = ask_amount_17; self.bid_price_17 = bid_price_17; self.bid_amount_17 = bid_amount_17
        self.ask_price_18 = ask_price_18; self.ask_amount_18 = ask_amount_18; self.bid_price_18 = bid_price_18; self.bid_amount_18 = bid_amount_18
        self.ask_price_19 = ask_price_19; self.ask_amount_19 = ask_amount_19; self.bid_price_19 = bid_price_19; self.bid_amount_19 = bid_amount_19
        self.ask_price_20 = ask_price_20; self.ask_amount_20 = ask_amount_20; self.bid_price_20 = bid_price_20; self.bid_amount_20 = bid_amount_20
        self.ask_price_21 = ask_price_21; self.ask_amount_21 = ask_amount_21; self.bid_price_21 = bid_price_21; self.bid_amount_21 = bid_amount_21
        self.ask_price_22 = ask_price_22; self.ask_amount_22 = ask_amount_22; self.bid_price_22 = bid_price_22; self.bid_amount_22 = bid_amount_22
        self.ask_price_23 = ask_price_23; self.ask_amount_23 = ask_amount_23; self.bid_price_23 = bid_price_23; self.bid_amount_23 = bid_amount_23
        self.ask_price_24 = ask_price_24; self.ask_amount_24 = ask_amount_24; self.bid_price_24 = bid_price_24; self.bid_amount_24 = bid_amount_24
        self.ask_price_25 = ask_price_25; self.ask_amount_25 = ask_amount_25; self.bid_price_25 = bid_price_25; self.bid_amount_25 = bid_amount_25
    
    cpdef Event derive(self):
        cdef OKXBookticker evt = OKXBookticker.__new__(OKXBookticker)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        evt.symbol = self.symbol
        evt.local_timestamp = self.local_timestamp
        
        evt.ask_price_1 = self.ask_price_1; evt.ask_amount_1 = self.ask_amount_1; evt.bid_price_1 = self.bid_price_1; evt.bid_amount_1 = self.bid_amount_1
        evt.ask_price_2 = self.ask_price_2; evt.ask_amount_2 = self.ask_amount_2; evt.bid_price_2 = self.bid_price_2; evt.bid_amount_2 = self.bid_amount_2
        evt.ask_price_3 = self.ask_price_3; evt.ask_amount_3 = self.ask_amount_3; evt.bid_price_3 = self.bid_price_3; evt.bid_amount_3 = self.bid_amount_3
        evt.ask_price_4 = self.ask_price_4; evt.ask_amount_4 = self.ask_amount_4; evt.bid_price_4 = self.bid_price_4; evt.bid_amount_4 = self.bid_amount_4
        evt.ask_price_5 = self.ask_price_5; evt.ask_amount_5 = self.ask_amount_5; evt.bid_price_5 = self.bid_price_5; evt.bid_amount_5 = self.bid_amount_5
        evt.ask_price_6 = self.ask_price_6; evt.ask_amount_6 = self.ask_amount_6; evt.bid_price_6 = self.bid_price_6; evt.bid_amount_6 = self.bid_amount_6
        evt.ask_price_7 = self.ask_price_7; evt.ask_amount_7 = self.ask_amount_7; evt.bid_price_7 = self.bid_price_7; evt.bid_amount_7 = self.bid_amount_7
        evt.ask_price_8 = self.ask_price_8; evt.ask_amount_8 = self.ask_amount_8; evt.bid_price_8 = self.bid_price_8; evt.bid_amount_8 = self.bid_amount_8
        evt.ask_price_9 = self.ask_price_9; evt.ask_amount_9 = self.ask_amount_9; evt.bid_price_9 = self.bid_price_9; evt.bid_amount_9 = self.bid_amount_9
        evt.ask_price_10 = self.ask_price_10; evt.ask_amount_10 = self.ask_amount_10; evt.bid_price_10 = self.bid_price_10; evt.bid_amount_10 = self.bid_amount_10
        evt.ask_price_11 = self.ask_price_11; evt.ask_amount_11 = self.ask_amount_11; evt.bid_price_11 = self.bid_price_11; evt.bid_amount_11 = self.bid_amount_11
        evt.ask_price_12 = self.ask_price_12; evt.ask_amount_12 = self.ask_amount_12; evt.bid_price_12 = self.bid_price_12; evt.bid_amount_12 = self.bid_amount_12
        evt.ask_price_13 = self.ask_price_13; evt.ask_amount_13 = self.ask_amount_13; evt.bid_price_13 = self.bid_price_13; evt.bid_amount_13 = self.bid_amount_13
        evt.ask_price_14 = self.ask_price_14; evt.ask_amount_14 = self.ask_amount_14; evt.bid_price_14 = self.bid_price_14; evt.bid_amount_14 = self.bid_amount_14
        evt.ask_price_15 = self.ask_price_15; evt.ask_amount_15 = self.ask_amount_15; evt.bid_price_15 = self.bid_price_15; evt.bid_amount_15 = self.bid_amount_15
        evt.ask_price_16 = self.ask_price_16; evt.ask_amount_16 = self.ask_amount_16; evt.bid_price_16 = self.bid_price_16; evt.bid_amount_16 = self.bid_amount_16
        evt.ask_price_17 = self.ask_price_17; evt.ask_amount_17 = self.ask_amount_17; evt.bid_price_17 = self.bid_price_17; evt.bid_amount_17 = self.bid_amount_17
        evt.ask_price_18 = self.ask_price_18; evt.ask_amount_18 = self.ask_amount_18; evt.bid_price_18 = self.bid_price_18; evt.bid_amount_18 = self.bid_amount_18
        evt.ask_price_19 = self.ask_price_19; evt.ask_amount_19 = self.ask_amount_19; evt.bid_price_19 = self.bid_price_19; evt.bid_amount_19 = self.bid_amount_19
        evt.ask_price_20 = self.ask_price_20; evt.ask_amount_20 = self.ask_amount_20; evt.bid_price_20 = self.bid_price_20; evt.bid_amount_20 = self.bid_amount_20
        evt.ask_price_21 = self.ask_price_21; evt.ask_amount_21 = self.ask_amount_21; evt.bid_price_21 = self.bid_price_21; evt.bid_amount_21 = self.bid_amount_21
        evt.ask_price_22 = self.ask_price_22; evt.ask_amount_22 = self.ask_amount_22; evt.bid_price_22 = self.bid_price_22; evt.bid_amount_22 = self.bid_amount_22
        evt.ask_price_23 = self.ask_price_23; evt.ask_amount_23 = self.ask_amount_23; evt.bid_price_23 = self.bid_price_23; evt.bid_amount_23 = self.bid_amount_23
        evt.ask_price_24 = self.ask_price_24; evt.ask_amount_24 = self.ask_amount_24; evt.bid_price_24 = self.bid_price_24; evt.bid_amount_24 = self.bid_amount_24
        evt.ask_price_25 = self.ask_price_25; evt.ask_amount_25 = self.ask_amount_25; evt.bid_price_25 = self.bid_price_25; evt.bid_amount_25 = self.bid_amount_25
        return evt

# =============================================================================
# OKXTrades (已优化)
# =============================================================================
cdef class OKXTrades(Event):
    def __init__(
        self,
        long long timestamp = 0,
        str symbol = "",
        long long trade_id = 0,
        double price = 0.0,
        double size = 0.0,
        str side = "",
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.trade_id = trade_id
        self.price = price
        self.size = size
        self.side = side

    def __repr__(self):
        return (f"OKXTrades(timestamp={self.timestamp}, symbol={self.symbol}, "
                f"trade_id={self.trade_id}, price={self.price}, size={self.size}, side={self.side})")

    cpdef Event derive(self):
        cdef OKXTrades evt = OKXTrades.__new__(OKXTrades)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        evt.symbol = self.symbol
        evt.trade_id = self.trade_id
        evt.price = self.price
        evt.size = self.size
        evt.side = self.side
        return evt

# =============================================================================
# OKXFundingRate (【本次新增优化】)
# =============================================================================
cdef class OKXFundingRate(Event):
    def __init__(
        self,
        long long timestamp = 0,
        str symbol = "",
        double funding_rate = 0.0,
        double price = 0.0,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.funding_rate = funding_rate
        self.price = price

    cpdef Event derive(self):
        # 极速拷贝
        cdef OKXFundingRate evt = OKXFundingRate.__new__(OKXFundingRate)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        evt.symbol = self.symbol
        evt.funding_rate = self.funding_rate
        evt.price = self.price
        return evt

# =============================================================================
# OKXDelivery (【本次新增优化】)
# =============================================================================
cdef class OKXDelivery(Event):
    def __init__(
        self,
        long long timestamp = 0,
        str symbol = "",
        double price = 0.0,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.price = price

    cpdef Event derive(self):
        cdef OKXDelivery evt = OKXDelivery.__new__(OKXDelivery)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        evt.symbol = self.symbol
        evt.price = self.price
        return evt

# =============================================================================
# OKXPremium (【本次新增优化】)
# =============================================================================
cdef class OKXPremium(Event):
    def __init__(
        self,
        long long timestamp = 0,
        str symbol = "",
        double premium = 0.0,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.premium = premium

    cpdef Event derive(self):
        cdef OKXPremium evt = OKXPremium.__new__(OKXPremium)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        evt.symbol = self.symbol
        evt.premium = self.premium
        return evt