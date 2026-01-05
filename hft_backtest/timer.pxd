# hft_backtest/timer.pxd
# cython: language_level=3

from hft_backtest.event cimport Event

cdef class Timer(Event):
    # 覆盖基类的 derive 方法
    cpdef Event derive(self)