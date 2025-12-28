# cython: language_level=3

from hft_backtest.matcher cimport MatchEngine
from hft_backtest.order cimport Order
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades, OKXDelivery

cdef class OKXMatcher(MatchEngine):
    cdef public str symbol
    cdef public double taker_fee
    cdef public double maker_fee
    
    cdef public long PRICE_SCALAR
    cdef public double INIT_RANK
    
    cdef public long best_bid_price_int
    cdef public long best_ask_price_int
    
    cdef public list buy_book
    cdef public list sell_book
    
    # 引用 EventEngine 用于推送回报
    cdef EventEngine event_engine

    # --- C 内部方法 ---
    cdef long to_int_price(self, double price)
    cdef void _add_order(self, Order order)
    cdef bint _remove_order(self, Order order)
    cdef void fill_order(self, Order order, double filled_price, bint is_taker)
    cdef void cancel_order(self, Order order)
    
    # [新增] 高性能二分查找档位量
    cdef double _get_level_volume(self, OKXBookticker event, bint is_ask, long price_int)

    # --- 接口实现 ---
    cpdef start(self, EventEngine engine)
    cpdef on_order(self, Order order)
    cpdef on_bookticker(self, OKXBookticker event)
    cpdef on_trade(self, OKXTrades event)
    cpdef on_delivery(self, OKXDelivery event)