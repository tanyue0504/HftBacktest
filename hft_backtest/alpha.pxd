# hft_backtest/alpha.pxd
# cython: language_level=3

from hft_backtest.event cimport Event


cdef class AlphaSignal(Event):
    cdef public str name
    cdef public str symbol
    cdef public long long horizon
    cdef public double value
