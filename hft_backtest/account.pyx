# cython: language_level=3

from hft_backtest.event cimport Event
from hft_backtest.order cimport Order

cdef class Account:
    def __init__(self):
        pass

    cpdef void on_order(self, Order order):
        pass

    cpdef dict get_positions(self):
        return {}

    cpdef dict get_orders(self):
        return {}
        
    cpdef dict get_prices(self):
        return {}

    cpdef double get_balance(self):
        return 0.0

    cpdef double get_equity(self):
        return 0.0