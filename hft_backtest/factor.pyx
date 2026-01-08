# hft_backtest/factor.pyx
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False

from hft_backtest.event cimport Event

cdef class FactorSignal(Event):
    """
    通用因子信号协议
    用于 Client 向 Server 发送计算好的因子值。
    """
    def __init__(self, str symbol, double value):
        # timestamp 默认为 0，等待 EventEngine 在 put 时自动赋值（或经过 DelayBus 赋值）
        super().__init__(0)
        self.symbol = symbol
        self.value = value

    def __repr__(self):
        return f"FactorSignal(symbol='{self.symbol}', value={self.value:.4f}, ts={self.timestamp})"

    cpdef Event derive(self):
        # 实现深拷贝逻辑，用于跨线程或延迟队列时保持状态独立
        cdef FactorSignal evt = FactorSignal.__new__(FactorSignal)
        evt.timestamp = 0
        evt.source = 0
        evt.producer = 0
        evt.symbol = self.symbol
        evt.value = self.value
        return evt