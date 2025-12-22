# cython: language_level=3

from hft_backtest.event cimport Event
from hft_backtest.order cimport Order

cdef class Account:
    # 声明基类提供的 C 接口
    cpdef void on_order(self, Order order)
    
    # 查询接口
    cpdef dict get_positions(self)
    cpdef dict get_orders(self)
    cpdef dict get_prices(self)  # 之前漏了这个，补上
    cpdef double get_balance(self)
    cpdef double get_equity(self)