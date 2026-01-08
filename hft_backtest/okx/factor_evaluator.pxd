# cython: language_level=3

from hft_backtest.event_engine cimport Component, EventEngine
from hft_backtest.factor cimport FactorSignal
from hft_backtest.okx.event cimport OKXBookticker, OKXTrades


cdef class FactorEvaluator(Component):
    cdef public object event_engine
    cdef public long long horizon
    cdef public int max_store
    cdef public bint enable_store

    cdef dict _sym
    cdef long long _global_first_ts
    cdef long long _global_last_ts

    cpdef start(self, EventEngine engine)
    cpdef stop(self)

    cpdef on_bookticker(self, OKXBookticker event)
    cpdef on_trades(self, OKXTrades event)
    cpdef on_factor(self, FactorSignal signal)

    cpdef reset(self)
    cpdef list symbols(self)
    cpdef dict get_symbol_stats(self, str symbol)
    cpdef dict get_stats(self)
    cpdef str format_report(self, str symbol=*, int max_symbols=*)
    cpdef print_report(self, str symbol=*, int max_symbols=*)
