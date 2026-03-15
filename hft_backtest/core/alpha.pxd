# hft_backtest/core/alpha.pxd
# cython: language_level=3

from hft_backtest.core.event cimport Event


cdef class AlphaSignal(Event):
    cdef public str name
    cdef public str symbol
    cdef public long long horizon
    cdef public double value
