# cython: language_level=3

from hft_backtest.event cimport Event

cdef class OKXBookticker(Event):
    cdef public str exchange
    cdef public str symbol
    cdef public long long local_timestamp
    
    # Depth 1-5
    cdef public double ask_price_1, ask_amount_1, bid_price_1, bid_amount_1
    cdef public double ask_price_2, ask_amount_2, bid_price_2, bid_amount_2
    cdef public double ask_price_3, ask_amount_3, bid_price_3, bid_amount_3
    cdef public double ask_price_4, ask_amount_4, bid_price_4, bid_amount_4
    cdef public double ask_price_5, ask_amount_5, bid_price_5, bid_amount_5
    
    # Depth 6-10
    cdef public double ask_price_6, ask_amount_6, bid_price_6, bid_amount_6
    cdef public double ask_price_7, ask_amount_7, bid_price_7, bid_amount_7
    cdef public double ask_price_8, ask_amount_8, bid_price_8, bid_amount_8
    cdef public double ask_price_9, ask_amount_9, bid_price_9, bid_amount_9
    cdef public double ask_price_10, ask_amount_10, bid_price_10, bid_amount_10

    # Depth 11-15
    cdef public double ask_price_11, ask_amount_11, bid_price_11, bid_amount_11
    cdef public double ask_price_12, ask_amount_12, bid_price_12, bid_amount_12
    cdef public double ask_price_13, ask_amount_13, bid_price_13, bid_amount_13
    cdef public double ask_price_14, ask_amount_14, bid_price_14, bid_amount_14
    cdef public double ask_price_15, ask_amount_15, bid_price_15, bid_amount_15

    # Depth 16-20
    cdef public double ask_price_16, ask_amount_16, bid_price_16, bid_amount_16
    cdef public double ask_price_17, ask_amount_17, bid_price_17, bid_amount_17
    cdef public double ask_price_18, ask_amount_18, bid_price_18, bid_amount_18
    cdef public double ask_price_19, ask_amount_19, bid_price_19, bid_amount_19
    cdef public double ask_price_20, ask_amount_20, bid_price_20, bid_amount_20

    # Depth 21-25
    cdef public double ask_price_21, ask_amount_21, bid_price_21, bid_amount_21
    cdef public double ask_price_22, ask_amount_22, bid_price_22, bid_amount_22
    cdef public double ask_price_23, ask_amount_23, bid_price_23, bid_amount_23
    cdef public double ask_price_24, ask_amount_24, bid_price_24, bid_amount_24
    cdef public double ask_price_25, ask_amount_25, bid_price_25, bid_amount_25

cdef class OKXTrades(Event):
    cdef public str symbol
    cdef public long long trade_id  # <--- 修改为 64位整数
    cdef public double price
    cdef public double size
    cdef public str side

cdef class OKXFundingRate(Event):
    cdef public str symbol
    cdef public double funding_rate
    cdef public double price

cdef class OKXDelivery(Event):
    cdef public str symbol
    cdef public double price

cdef class OKXPremium(Event):
    cdef public str symbol
    cdef public double premium