from hft_backtest.account cimport Account
from hft_backtest.event_engine cimport EventEngine
from hft_backtest.order cimport Order
from hft_backtest.okx.event cimport OKXTrades, OKXFundingRate, OKXDelivery

cdef class OKXAccount(Account):
    cdef public double cash_balance
    cdef public object position_dict
    cdef public object order_dict
    # 【新增声明】必须在这里声明，否则 .pyx 里无法使用
    cdef public object finished_order_ids 
    cdef public object price_dict
    
    cdef public object total_turnover
    cdef public object total_commission
    cdef public object total_funding_fee
    cdef public object net_cash_flow
    cdef public object total_trade_count

    cpdef start(self, EventEngine engine)
    cpdef stop(self)
    cpdef void on_order(self, Order order)
    cpdef void on_trade_data(self, OKXTrades event)
    cpdef void on_funding_data(self, OKXFundingRate event)
    cpdef void on_delivery_data(self, OKXDelivery event)
    
    cpdef dict get_orders(self)
    cpdef dict get_positions(self)
    cpdef dict get_prices(self)
    cpdef double get_balance(self)
    cpdef double get_position_cashvalue(self)
    cpdef double get_equity(self)
    cpdef double get_total_margin(self)
    
    cpdef double get_total_turnover(self)
    cpdef int get_total_trade_count(self)
    cpdef double get_total_commission(self)
    cpdef double get_total_funding_fee(self)
    cpdef double get_total_trade_pnl(self)
    
    cdef double _get_position_cashvalue(self)