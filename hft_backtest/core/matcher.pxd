# cython: language_level=3
from hft_backtest.core.event_engine cimport Component, EventEngine
from hft_backtest.core.order cimport Order

cdef class MatchEngine(Component):
    cpdef on_order(self, Order order)