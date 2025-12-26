# cython: language_level=3
from hft_backtest.matcher cimport MatchEngine
from hft_backtest.order cimport Order
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades, OKXDelivery

cdef class OKXMatcher(MatchEngine):
    cdef public str symbol
    cdef public double taker_fee
    cdef public double maker_fee
    
    # 必须显式声明 event_engine
    cdef public EventEngine event_engine
    
    # 价格转换为整数后的缓存
    cdef public long best_bid_price_int
    cdef public long best_ask_price_int
    
    # 订单账本
    cdef public list buy_book
    cdef public list sell_book
    
    # 内部常量
    cdef public long PRICE_SCALAR
    cdef double INIT_RANK

    # 方法定义
    cpdef start(self, EventEngine engine)
    cdef long to_int_price(self, double price)
    cdef void _add_order(self, Order order)
    cdef bint _remove_order(self, Order order)
    cdef void fill_order(self, Order order, double filled_price, bint is_taker)
    cdef void cancel_order(self, Order order)
    
    # 事件处理
    cpdef on_order(self, Order order)
    cpdef on_bookticker(self, OKXBookticker event)
    cpdef on_trade(self, OKXTrades event)
    cpdef on_delivery(self, OKXDelivery event)