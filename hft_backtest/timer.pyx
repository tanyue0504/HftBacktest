# hft_backtest/timer.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.event cimport Event

cdef class Timer(Event):
    """
    高性能定时器事件 (Cython 重构版)
    """
    def __init__(self, long long timestamp = 0):
        self.timestamp = timestamp
        self.source = 0
        self.producer = 0

    # 【核心优化】手动实现 derive，绕过 copy.copy
    cpdef Event derive(self):
        # 1. 极速分配内存 (绕过 __init__)
        cdef Timer evt = Timer.__new__(Timer)
        
        # 2. 赋值 (Timer 没有额外载荷，只需要重置头部)
        # 注意：DelayBus 稍后会用 event.timestamp 覆盖 evt.timestamp，
        # 所以这里设为 0 或者复制 self.timestamp 都可以。
        # 为了符合 derive "重置路由信息" 的语义，我们设为 0。
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        
        return evt

    def __repr__(self):
        return f"<Timer Event | timestamp: {self.timestamp}>"