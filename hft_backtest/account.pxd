# hft_backtest/account.pxd
# cython: language_level=3

from hft_backtest.order cimport Order
from hft_backtest.event_engine cimport Component, EventEngine

cdef class Account(Component):
    # --- 核心事件回调 (必须实现) ---
    cpdef void on_order(self, Order order)
    
    # --- 状态查询接口 (必须实现) ---
    cpdef dict get_positions(self)
    cpdef dict get_orders(self)
    cpdef dict get_prices(self)
    cpdef double get_balance(self)
    cpdef double get_equity(self)
    
    # --- 统计接口 (Recorder 依赖，必须实现) ---
    cpdef double get_total_turnover(self)
    cpdef double get_total_commission(self)
    cpdef double get_total_funding_fee(self)
    cpdef double get_total_trade_pnl(self)
    cpdef int get_total_trade_count(self)