# hft_backtest/factor.pxd
# cython: language_level=3

from hft_backtest.event cimport Event

cdef class FactorSignal(Event):
    cdef public str name
    cdef public str symbol
    cdef public double value